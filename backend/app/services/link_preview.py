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
MAX_JSON_LD_CHARS = 200_000

Resolver = Callable[[str, int], Awaitable[list[str]]]


class PreviewError(Exception):
    pass


class UnsafeUrl(PreviewError):
    """Not http(s), or points to a private / local / reserved address."""


class FetchFailed(PreviewError):
    """The site didn't answer usefully (timeout, error status, too big...)."""


@dataclass(frozen=True)
class Fetched:
    url: str  # the logical URL (by host name), after redirects
    content_type: str
    body: bytes
    charset: str | None = None  # from the Content-Type header


@dataclass(frozen=True)
class Preview:
    title: str | None = None
    price: Decimal | None = None
    image_url: str | None = None


# --- SSRF guard ---------------------------------------------------------------


async def system_resolver(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


ALLOWED_PORTS = {80, 443, 8080, 8443}
# Ranges whose ``is_global`` is True in Python but that can reach local addresses.
_BLOCKED_V6 = (
    ipaddress.ip_network("64:ff9b::/96"),  # NAT64 (e.g. 64:ff9b::7f00:1 -> 127.0.0.1)
    ipaddress.ip_network("::/96"),  # IPv4-compatible (deprecated), e.g. ::127.0.0.1
)


@dataclass(frozen=True)
class Target:
    """A checked URL and the exact IP address the connection must go to."""

    url: str
    scheme: str
    hostname: str
    port: int
    ip: str


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        elif any(ip in net for net in _BLOCKED_V6):
            return False
    return ip.is_global and not ip.is_multicast


async def ensure_public(url: str, resolve: Resolver = system_resolver) -> Target:
    """Validate ``url`` and resolve it ONCE; the caller must connect to ``Target.ip``.

    Connecting by IP (not by name) closes the DNS-rebinding gap between check and use.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeUrl("only http(s) links are supported")
    if parsed.username or parsed.password:
        raise UnsafeUrl("links with credentials are not supported")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeUrl("invalid port") from exc
    if port not in ALLOWED_PORTS:
        raise UnsafeUrl("only standard web ports are supported")
    try:
        addresses = await resolve(parsed.hostname, port)
    except (OSError, UnicodeError) as exc:
        raise FetchFailed("host not found") from exc
    if not addresses:
        raise FetchFailed("host not found")
    try:
        if not all(_is_public(a) for a in addresses):
            raise UnsafeUrl("private or local addresses are not allowed")
    except ValueError as exc:
        raise UnsafeUrl("invalid address") from exc
    return Target(url, parsed.scheme, parsed.hostname, port, addresses[0].split("%")[0])


def _pinned_request(target: Target) -> tuple[str, dict[str, str], dict[str, str]]:
    """URL pointing at the checked IP, plus the Host header and TLS server name."""
    parsed = urlparse(target.url)
    host = f"[{target.ip}]" if ":" in target.ip else target.ip
    default_port = 443 if target.scheme == "https" else 80
    netloc = host if target.port == default_port else f"{host}:{target.port}"
    pinned = parsed._replace(netloc=netloc).geturl()
    host_header = (
        target.hostname if target.port == default_port else f"{target.hostname}:{target.port}"
    )
    extensions = {"sni_hostname": target.hostname} if target.scheme == "https" else {}
    return pinned, {"Host": host_header}, extensions


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
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "pl,uk;q=0.8",
            # No compression: a tiny gzip/brotli chunk could expand to a huge one in memory.
            "Accept-Encoding": "identity",
        }
        async with httpx.AsyncClient(
            transport=self._transport,
            follow_redirects=False,
            timeout=TIMEOUT_SECONDS,
            trust_env=False,  # no env proxies (would bypass the IP check), no .netrc
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                target = await ensure_public(url, self._resolve)
                pinned_url, host_header, extensions = _pinned_request(target)
                try:
                    request = client.build_request(
                        "GET", pinned_url, headers={**headers, **host_header}, extensions=extensions
                    )
                    resp = await client.send(request, stream=True)
                    try:
                        if resp.is_redirect and "location" in resp.headers:
                            url = urljoin(url, resp.headers["location"])
                            continue
                        if resp.status_code != 200:
                            raise FetchFailed(f"status {resp.status_code}")
                        # We asked for identity; refuse compressed bodies before reading
                        # anything, so nothing gets decompressed in memory.
                        if resp.headers.get("content-encoding", "identity") not in ("identity", ""):
                            raise FetchFailed("compressed responses are not supported")
                        body = bytearray()
                        async for chunk in resp.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > max_bytes:
                                raise FetchFailed("response too large")
                        raw_type = resp.headers.get("content-type", "")
                        content_type = raw_type.split(";")[0].strip().lower()
                        charset = re.search(r"charset=([\w-]+)", raw_type, re.IGNORECASE)
                        return Fetched(
                            url, content_type, bytes(body), charset.group(1) if charset else None
                        )
                    finally:
                        await resp.aclose()
                except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
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
        value = Decimal(text)
        if value.is_finite():
            value = value.quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    if not value.is_finite():  # "NaN" would break the comparison below
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
        if len(raw) > MAX_JSON_LD_CHARS:
            continue
        try:
            products += _products(json.loads(raw))
        except (ValueError, RecursionError):  # broken or absurdly nested JSON
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
    """Decode with the header charset, else <meta charset>, else UTF-8."""
    encoding = fetched.charset
    if not encoding:
        match = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', fetched.body[:4096], re.I)
        encoding = match.group(1).decode() if match else "utf-8"
    try:
        return fetched.body.decode(encoding, errors="replace")
    except (LookupError, UnicodeError, TypeError):  # unknown or non-text codec (e.g. idna)
        return fetched.body.decode("utf-8", errors="replace")
