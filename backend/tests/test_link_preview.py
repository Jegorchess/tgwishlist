"""AF-1: autofill a wish from a shop link (issue #15)."""

import io
from decimal import Decimal

import httpx
import pytest
from PIL import Image

from app.main import app
from app.services.link_preview import (
    MAX_REDIRECTS,
    FetchFailed,
    PageFetcher,
    UnsafeUrl,
    ensure_public,
    get_fetcher,
    parse_preview,
    parse_price,
)
from tests.helpers import auth, make_init_data

PUBLIC_IP = "93.184.215.14"


async def public_resolver(host: str, port: int) -> list[str]:
    return [PUBLIC_IP]


def resolver_for(mapping: dict[str, str]):
    async def resolve(host: str, port: int) -> list[str]:
        return [mapping.get(host, PUBLIC_IP)]

    return resolve


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "green").save(buf, "PNG")
    return buf.getvalue()


SHOP_HTML = """<!doctype html><html><head>
<meta charset="utf-8">
<title>Słuchawki XM5 | Sklep</title>
<meta property="og:title" content="Słuchawki Sony WH-1000XM5">
<meta property="og:image" content="/img/xm5.png">
<meta property="product:price:amount" content="1 299,99">
<meta property="product:price:currency" content="PLN">
</head><body>...</body></html>"""

JSON_LD_HTML = """<html><head><title>Fallback</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "WebPage", "name": "page"},
  {"@type": "Product", "name": "Lego Technic 42115",
   "image": ["https://cdn.example.com/lego.jpg"],
   "offers": {"@type": "Offer", "price": "1899.00", "priceCurrency": "PLN"}}
]}
</script></head></html>"""


# --- parsing --------------------------------------------------------------------


def test_open_graph_preview():
    preview = parse_preview(SHOP_HTML, "https://shop.example.com/p/1")

    assert preview.title == "Słuchawki Sony WH-1000XM5"
    assert preview.price == Decimal("1299.99")
    assert preview.image_url == "https://shop.example.com/img/xm5.png"


def test_json_ld_product_preview():
    preview = parse_preview(JSON_LD_HTML, "https://lego.example.com/")

    assert preview.title == "Lego Technic 42115"
    assert preview.price == Decimal("1899.00")
    assert preview.image_url == "https://cdn.example.com/lego.jpg"


def test_price_only_in_pln():
    html = SHOP_HTML.replace('content="PLN"', 'content="EUR"')

    assert parse_preview(html, "https://shop.example.com/").price is None


def test_title_falls_back_to_title_tag():
    preview = parse_preview("<title>  Just   a page </title>", "https://x.example/")

    assert preview.title == "Just a page"
    assert preview.price is None
    assert preview.image_url is None


def test_nothing_useful():
    assert parse_preview("not html at all", "https://x.example/") == parse_preview(
        "", "https://x.example/"
    )


def test_non_http_image_is_dropped():
    html = '<meta property="og:image" content="javascript:alert(1)">'

    assert parse_preview(html, "https://x.example/").image_url is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1299.99", Decimal("1299.99")),
        ("1 299,99 zł", Decimal("1299.99")),
        ("1.299,99", Decimal("1299.99")),
        ("1,299.99", Decimal("1299.99")),
        (1299, Decimal("1299.00")),
        ("99 PLN", Decimal("99.00")),
        ("-5", None),
        ("free", None),
        (None, None),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


# --- SSRF guard -----------------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "172.16.0.1",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fd00::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
    ],
)
async def test_private_addresses_are_refused(address):
    with pytest.raises(UnsafeUrl):
        await ensure_public("http://shop.example.com/", resolver_for({"shop.example.com": address}))


@pytest.mark.parametrize(
    "url", ["ftp://example.com/x", "file:///etc/passwd", "javascript:alert(1)", "http://u:p@x.com/"]
)
async def test_bad_schemes_are_refused(url):
    with pytest.raises(UnsafeUrl):
        await ensure_public(url, public_resolver)


async def test_public_address_is_allowed():
    await ensure_public("https://shop.example.com/p", public_resolver)


# --- fetcher --------------------------------------------------------------------


def fetcher(handler, resolve=public_resolver) -> PageFetcher:
    return PageFetcher(transport=httpx.MockTransport(handler), resolve=resolve)


async def test_follows_redirect_to_public_host():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/short":
            return httpx.Response(302, headers={"location": "https://shop.example.com/p/1"})
        return httpx.Response(200, html=SHOP_HTML)

    page = await fetcher(handler).get("https://sho.rt/short", max_bytes=10_000, accept="*/*")

    assert page.url == "https://shop.example.com/p/1"
    assert "Sony" in page.body.decode()


async def test_redirect_to_private_address_is_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://internal.local/admin"})

    resolve = resolver_for({"internal.local": "10.0.0.1"})
    with pytest.raises(UnsafeUrl):
        await fetcher(handler, resolve).get("https://sho.rt/x", max_bytes=10_000, accept="*/*")


async def test_too_many_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        n = int(request.url.params.get("n", "0"))
        return httpx.Response(302, headers={"location": f"https://loop.example/?n={n + 1}"})

    with pytest.raises(FetchFailed):
        await fetcher(handler).get("https://loop.example/", max_bytes=10_000, accept="*/*")
    assert MAX_REDIRECTS == 3


async def test_response_size_is_capped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 5000)

    with pytest.raises(FetchFailed):
        await fetcher(handler).get("https://big.example/", max_bytes=1000, accept="*/*")


async def test_error_status_fails():
    with pytest.raises(FetchFailed):
        await fetcher(lambda r: httpx.Response(403)).get(
            "https://shop.example.com/", max_bytes=1000, accept="*/*"
        )


# --- API --------------------------------------------------------------------------


@pytest.fixture
def fake_site():
    """Serve SHOP_HTML at /p/1 and a PNG at /img/xm5.png for the API under test."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/1":
            return httpx.Response(200, html=SHOP_HTML)
        if request.url.path == "/img/xm5.png":
            return httpx.Response(200, content=png_bytes(), headers={"content-type": "image/png"})
        if request.url.path == "/text":
            return httpx.Response(200, text="hello", headers={"content-type": "text/plain"})
        return httpx.Response(404)

    app.dependency_overrides[get_fetcher] = lambda: fetcher(handler)
    yield
    app.dependency_overrides.pop(get_fetcher, None)


async def test_preview_endpoint(client, fake_site):
    resp = await client.post(
        "/api/link-preview", json={"url": "https://shop.example.com/p/1"}, headers=auth()
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "title": "Słuchawki Sony WH-1000XM5",
        "price": "1299.99",
        "image_url": "https://shop.example.com/img/xm5.png",
    }


async def test_preview_of_unreachable_page_is_empty(client, fake_site):
    resp = await client.post(
        "/api/link-preview", json={"url": "https://shop.example.com/missing"}, headers=auth()
    )

    assert resp.status_code == 200
    assert resp.json() == {"title": None, "price": None, "image_url": None}


async def test_preview_of_private_address_is_422(client):
    app.dependency_overrides[get_fetcher] = lambda: fetcher(
        lambda r: httpx.Response(200), resolver_for({"router.lan": "192.168.0.1"})
    )
    try:
        resp = await client.post(
            "/api/link-preview", json={"url": "http://router.lan/"}, headers=auth()
        )
    finally:
        app.dependency_overrides.pop(get_fetcher, None)

    assert resp.status_code == 422


async def test_image_proxy_returns_image(client, fake_site):
    resp = await client.get(
        "/api/link-preview/image",
        params={"url": "https://shop.example.com/img/xm5.png"},
        headers=auth(),
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(resp.content)).format == "PNG"


async def test_image_proxy_refuses_non_images(client, fake_site):
    resp = await client.get(
        "/api/link-preview/image", params={"url": "https://shop.example.com/text"}, headers=auth()
    )

    assert resp.status_code == 502


async def test_stranger_cannot_use_preview(client, fake_site):
    stranger = auth(make_init_data(user={"id": 777, "first_name": "X"}))

    resp = await client.post(
        "/api/link-preview", json={"url": "https://shop.example.com/p/1"}, headers=stranger
    )

    assert resp.status_code == 403


# --- regressions from security review ----------------------------------------------


async def test_connects_to_the_checked_ip_not_a_second_lookup():
    """DNS rebinding: a second lookup would return 127.0.0.1, but we never do one."""
    answers = iter([PUBLIC_IP, "127.0.0.1"])
    seen: list[httpx.Request] = []

    async def rebinding_resolver(host: str, port: int) -> list[str]:
        return [next(answers)]

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, html=SHOP_HTML)

    page = await fetcher(handler, rebinding_resolver).get(
        "https://shop.example.com/p/1", max_bytes=10_000, accept="*/*"
    )

    assert page.url == "https://shop.example.com/p/1"
    [request] = seen
    assert request.url.host == PUBLIC_IP
    assert request.headers["host"] == "shop.example.com"
    assert request.extensions["sni_hostname"] == "shop.example.com"


@pytest.mark.parametrize("address", ["64:ff9b::7f00:1", "::127.0.0.1"])
async def test_ipv6_tricks_are_refused(address):
    with pytest.raises(UnsafeUrl):
        await ensure_public("http://x.example/", resolver_for({"x.example": address}))


@pytest.mark.parametrize(
    "url", ["http://a.example:99999/", "http://a.example:22/", "http://a.example:6379/"]
)
async def test_odd_ports_are_refused(url):
    with pytest.raises(UnsafeUrl):
        await ensure_public(url, public_resolver)


async def test_compressed_response_is_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, content=b"\x1f\x8b...", headers={"content-encoding": "gzip"})

    with pytest.raises(FetchFailed):
        await fetcher(handler).get("https://shop.example.com/", max_bytes=10_000, accept="*/*")


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_parse_price_special_values(raw):
    assert parse_price(raw) is None


def test_pathological_json_ld_is_ignored():
    html = '<script type="application/ld+json">' + "[" * 100_000 + "</script><title>Ok</title>"

    assert parse_preview(html, "https://x.example/").title == "Ok"


def test_weird_charset_falls_back_to_utf8():
    from app.services.link_preview import Fetched, decode_html

    page = Fetched("https://x.example/", "text/html", '<meta charset="idna">Привіт'.encode())

    assert "Привіт" in decode_html(page)


def test_header_charset_wins_over_meta():
    from app.services.link_preview import Fetched, decode_html

    body = '<meta charset="utf-8">Zażółć'.encode("iso-8859-2")
    page = Fetched("https://x.example/", "text/html", body, charset="iso-8859-2")

    assert "Zażółć" in decode_html(page)


async def test_image_proxy_refuses_svg(client):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    app.dependency_overrides[get_fetcher] = lambda: fetcher(
        lambda r: httpx.Response(200, content=svg, headers={"content-type": "image/svg+xml"})
    )
    try:
        resp = await client.get(
            "/api/link-preview/image", params={"url": "https://x.example/a.svg"}, headers=auth()
        )
    finally:
        app.dependency_overrides.pop(get_fetcher, None)

    assert resp.status_code == 502


async def test_image_proxy_sets_defensive_headers(client, fake_site):
    resp = await client.get(
        "/api/link-preview/image",
        params={"url": "https://shop.example.com/img/xm5.png"},
        headers=auth(),
    )

    assert resp.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert resp.headers["x-content-type-options"] == "nosniff"
