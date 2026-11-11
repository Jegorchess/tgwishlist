"""Autofill a wish from a shop link: title, price (PLN) and photo.

The server fetches a user-supplied URL, so every request is guarded against SSRF:
only http(s), only public IP addresses (checked again on every redirect), capped
size, redirects and time.
"""

import asyncio
import contextlib
import ipaddress
import json
import re
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 8.0
USER_AGENT = "Mozilla/5.0 (compatible; WishlistPreview/1.0)"
TITLE_MAX = 200
PRICE_MAX = Decimal("99999999.99")

Resolver = Callable[[str, int], Awaitable[list[str]]]


class PreviewError(Exception):
    pass


class UnsafeUrl(PreviewError):
    """Not http(s), or points to a private / local / reserved address."""


class FetchFailed(PreviewError):
    """The site didn't answer usefully (timeout, error status, too big...)."""


@dataclass(frozen=True)
class Fetched:
    url: str
    content_type: str
    body: bytes


@dataclass(frozen=True)
class Preview:
    title: str | None = None
    price: Decimal | None = None
    image_url: str | None = None


# --- SSRF guard ---------------------------------------------------------------


async def system_resolver(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


async def ensure_public(url: str, resolve: Resolver = system_resolver) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeUrl("only http(s) links are supported")
    if parsed.username or parsed.password:
        raise UnsafeUrl("links with credentials are not supported")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = await resolve(parsed.hostname, port)
    except OSError as exc:
        raise FetchFailed("host not found") from exc
    if not addresses:
        raise FetchFailed("host not found")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            raise UnsafeUrl("private or local addresses are not allowed")


# --- fetching -----------------------------------------------------------------


class PageFetcher:
    """HTTP GET with the SSRF guard on every hop and hard limits."""

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        resolve: Resolver = system_resolver,
    ) -> None:
        self._transport = transport
        self._resolve = resolve

    async def get(self, url: str, *, max_bytes: int, accept: str) -> Fetched:
        try:
            return await asyncio.wait_for(self._get(url, max_bytes, accept), TIMEOUT_SECONDS)
        except TimeoutError as exc:
            raise FetchFailed("timeout") from exc

    async def _get(self, url: str, max_bytes: int, accept: str) -> Fetched:
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "pl,uk;q=0.8"}
        async with httpx.AsyncClient(
            transport=self._transport, follow_redirects=False, timeout=TIMEOUT_SECONDS
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await ensure_public(url, self._resolve)
                try:
                    async with client.stream("GET", url, headers=headers) as resp:
                        if resp.is_redirect and "location" in resp.headers:
                            url = urljoin(url, resp.headers["location"])
                            continue
                        if resp.status_code != 200:
                            raise FetchFailed(f"status {resp.status_code}")
                        body = bytearray()
                        async for chunk in resp.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > max_bytes:
                                raise FetchFailed("response too large")
                        content_type = resp.headers.get("content-type", "").split(";")[0].strip()
                        return Fetched(str(resp.url), content_type.lower(), bytes(body))
                except httpx.HTTPError as exc:
                    raise FetchFailed(str(exc)) from exc
        raise FetchFailed("too many redirects")


def get_fetcher() -> PageFetcher:
    return PageFetcher()


# --- parsing ------------------------------------------------------------------


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.json_ld: list[str] = []
        self._in_title = False
        self._in_ld = False
        self._ld_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and "content" in a and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_ld = True
            self._ld_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_ld:
            self._in_ld = False
            self.json_ld.append("".join(self._ld_buf))

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._in_ld:
            self._ld_buf.append(data)


def _products(node: object) -> list[dict]:
    """All JSON-LD objects of @type Product (including inside @graph / lists)."""
    found: list[dict] = []
    if isinstance(node, list):
        for item in node:
            found += _products(item)
    elif isinstance(node, dict):
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "Product" in kinds:
            found.append(node)
        if "@graph" in node:
            found += _products(node["@graph"])
    return found


def parse_price(raw: object) -> Decimal | None:
    """'1 299,99' / '1299.99' / 1299 -> Decimal('1299.99'); None if not a sane price."""
    if raw is None:
        return None
    text = re.sub(r"[\s zł]|PLN", "", str(raw), flags=re.IGNORECASE)
    if "," in text and "." in text:  # 1.299,99 or 1,299.99
        text = (
            text.replace(".", "").replace(",", ".")
            if text.rfind(",") > text.rfind(".")
            else text.replace(",", "")
        )
    else:
        text = text.replace(",", ".")
    try:
        value = Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return value if Decimal(0) <= value <= PRICE_MAX else None


def _first_image(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return _first_image(value[0])
    if isinstance(value, dict):
        return _first_image(value.get("url") or value.get("contentUrl"))
    return None


def parse_preview(html: str, base_url: str) -> Preview:
    parser = _MetaParser()
    with contextlib.suppress(Exception):  # broken markup: use whatever was parsed
        parser.feed(html)
    meta = parser.meta

    products: list[dict] = []
    for raw in parser.json_ld:
        try:
            products += _products(json.loads(raw))
        except ValueError:
            continue
    product = products[0] if products else {}

    title = (
        meta.get("og:title")
        or meta.get("twitter:title")
        or (product.get("name") if isinstance(product.get("name"), str) else None)
        or parser.title
    )
    title = " ".join(title.split())[:TITLE_MAX] if title else None

    price: Decimal | None = None
    currency = (meta.get("product:price:currency") or meta.get("og:price:currency") or "").upper()
    amount = meta.get("product:price:amount") or meta.get("og:price:amount")
    if amount and currency == "PLN":
        price = parse_price(amount)
    if price is None and product:
        offers = product.get("offers")
        for offer in offers if isinstance(offers, list) else [offers]:
            if isinstance(offer, dict) and str(offer.get("priceCurrency", "")).upper() == "PLN":
                price = parse_price(offer.get("price") or offer.get("lowPrice"))
                if price is not None:
                    break
    if price is None and meta.get("pricecurrency", "").upper() == "PLN":  # microdata itemprop
        price = parse_price(meta.get("price"))

    image = meta.get("og:image") or meta.get("og:image:url") or meta.get("twitter:image")
    image = image or _first_image(product.get("image"))
    image_url = urljoin(base_url, image) if image else None
    if image_url and urlparse(image_url).scheme not in ("http", "https"):
        image_url = None

    return Preview(title=title or None, price=price, image_url=image_url)


def decode_html(fetched: Fetched) -> str:
    match = re.search(rb'charset=["\']?([\w-]+)', fetched.body[:4096])
    encoding = match.group(1).decode() if match else "utf-8"
    try:
        return fetched.body.decode(encoding, errors="replace")
    except LookupError:
        return fetched.body.decode("utf-8", errors="replace")
