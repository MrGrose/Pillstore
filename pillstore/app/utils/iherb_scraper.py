from __future__ import annotations

import argparse
import json
import logging
import random
import re
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import cloudscraper
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None

def _translate_en_ru(text: str) -> str:
    if not (text or "").strip():
        return text or ""
    try:
        return GoogleTranslator(source="en", target="ru").translate(text=text[:5000]) or text
    except Exception:
        return text


logger = logging.getLogger(__name__)
_playwright_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="playwright")
BASE = "https://www.iherb.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.iherb.com/",
}

REQUEST_TIMEOUT = 45
SLEEP_BETWEEN_REQUESTS = (2.0, 4.0)


def sleep_politely():
    time.sleep(random.uniform(*SLEEP_BETWEEN_REQUESTS))


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        pass


@dataclass
class ProductScraper:
    name: str | None = None
    name_en: str | None = None
    brand: str | None = None
    mpn: str | None = None
    price: float | None = None
    stock: int | None = 5
    url: str | None = None
    images: str | None = None
    category_path: list[str] | None = None
    description_left: str | None = None
    description_right: str | None = None


class IHerbScraper:
    def __init__(self, session: requests.Session | None = None):
        self.sess = session or cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
        self.sess.headers.update(HEADERS)
        self.sess.cookies.set("iher-pref1", "en-US")
        self.sess.cookies.set("iher-pref2", "US")

    def _normalize_www(self, url: str) -> str:
        pu = urlparse(url)
        if pu.netloc.startswith("de.iherb.com"):
            pu = pu._replace(netloc="www.iherb.com")
        return urlunparse(pu)

    def _is_cloudflare_challenge(self, resp: requests.Response) -> bool:
        if resp.status_code in (403, 503):
            return True
        text = (resp.text or "").lower()
        return (
            "just a moment" in text
            or "cf-browser-verification" in text
            or "checking your browser" in text
        )

    def _fetch_via_playwright(self, url: str) -> str | None:
        if not PLAYWRIGHT_AVAILABLE or sync_playwright is None:
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                context = browser.new_context(
                    locale="en-US",
                    user_agent=HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                context.add_cookies([
                    {"name": "iher-pref1", "value": "en-US", "domain": ".iherb.com", "path": "/"},
                    {"name": "iher-pref2", "value": "US", "domain": ".iherb.com", "path": "/"},
                ])
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            logger.warning("Playwright fallback не сработал: %s", e)
            return None

    def get(self, url: str):  # noqa: C901
        url = self._normalize_www(url)
        if not hasattr(self, "_ua_counter"):
            self._ua_counter = 0
        self._ua_counter += 1
        if self._ua_counter % 5 == 0:
            ua_list = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            ]
            self.sess.headers["User-Agent"] = random.choice(ua_list)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if "/search" in url or "/c/" in url:
                    self.sess.headers["Referer"] = "https://www.iherb.com/"

                resp = self.sess.get(url, timeout=(10, 60), allow_redirects=True)
                if resp.status_code == 403 or self._is_cloudflare_challenge(resp):
                    if PLAYWRIGHT_AVAILABLE:
                        html = _playwright_executor.submit(
                            self._fetch_via_playwright, url
                        ).result(timeout=70)
                        if html:
                            return _FakeResponse(html)
                    else:
                        logger.warning("Парсинг iHerb: 403, Playwright недоступен: %s", url)
                    if resp.status_code == 403:
                        raise requests.HTTPError(f"403 Forbidden for {url}")
                resp.raise_for_status()

                time.sleep(random.uniform(3, 6))
                return resp

            except requests.HTTPError:
                if PLAYWRIGHT_AVAILABLE:
                    html = _playwright_executor.submit(
                        self._fetch_via_playwright, url
                    ).result(timeout=70)
                    if html:
                        return _FakeResponse(html)
                raise
            except requests.exceptions.ReadTimeout:
                if attempt < max_retries - 1:
                    wait = 2**attempt + random.uniform(0, 1)
                    time.sleep(wait)
                    continue
                raise

    @staticmethod
    def build_search_url(query: str, page: int = 1) -> str:
        params = {"kw": query}
        url = f"{BASE}/search?{urlencode(params)}"
        if page > 1:
            url = IHerbScraper.set_query_param(url, "p", str(page))
        return url

    @staticmethod
    def set_query_param(url: str, key: str, value: str) -> str:
        parts = list(urlparse(url))
        qs = parse_qs(parts[4])
        qs[key] = [value]
        parts[4] = urlencode(qs, doseq=True)
        return urlunparse(parts)

    def iter_listing_pages(self, start_url: str, max_pages: int) -> Iterable[str]:
        seen = set()
        current = self._normalize_www(start_url)
        for _ in range(max_pages):
            if current in seen:
                break
            seen.add(current)
            yield current

            try:
                html = self.get(current).text
            except requests.HTTPError:
                break
            soup = BeautifulSoup(html, "lxml")
            next_link = soup.find("link", rel=lambda v: v and "next" in v.lower())
            if next_link and next_link.get("href"):
                current = self._normalize_www(urljoin(current, next_link["href"]))
                continue

            parsed = urlparse(current)
            qs = parse_qs(parsed.query)
            p = int(qs.get("p", ["1"])[0])
            p += 1
            current = self.set_query_param(current, "p", str(p))

    PRODUCT_LINK_PATTERNS = [
        re.compile(r"/pr/[^/?#]+", re.IGNORECASE),
        re.compile(r"/(?:gb|de|es|fr)/pr/[^/?#]+", re.IGNORECASE),
        re.compile(r"/prod/[^/?#]+", re.IGNORECASE),
    ]

    def extract_product_links(self, listing_html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(listing_html, "lxml")
        links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(rx.search(href) for rx in self.PRODUCT_LINK_PATTERNS):
                link = urljoin(base_url, href.split("?")[0])
                link = self._normalize_www(link)
                links.add(link)

        for tag in soup.find_all(attrs={"data-product-url": True}):
            href = tag.get("data-product-url")
            if href and any(rx.search(href) for rx in self.PRODUCT_LINK_PATTERNS):
                link = urljoin(base_url, href.split("?")[0])
                link = self._normalize_www(link)
                links.add(link)

        return sorted(links)

    def parse_product_page(self, url: str) -> ProductScraper | None:  # noqa: C901
        try:
            html = self.get(url).text
        except requests.HTTPError as e:
            logger.error("Парсинг iHerb: %s", e)
            return None

        try:
            return self._parse_product_page_html(url, html)
        except Exception as e:
            logger.exception("Парсинг iHerb: ошибка разбора страницы %s: %s", url, e)
            return None

    def _parse_product_page_html(self, url: str, html: str) -> ProductScraper:
        soup = BeautifulSoup(html, "lxml")
        product = ProductScraper(url=self._normalize_www(url))

        data = self._extract_jsonld_objects(soup)
        product.category_path = self._extract_breadcrumbs(
            data
        ) or self._extract_breadcrumbs_from_dom(soup)

        prod = self._find_first_by_type(data, "Product")
        if prod:
            product.name_en = prod.get("name") or product.name_en
            if product.name_en:
                product.name = _translate_en_ru(product.name_en)

            brand = prod.get("brand")
            if isinstance(brand, dict):
                product.brand = brand.get("name")
            elif isinstance(brand, str):
                product.brand = brand

            product.mpn = prod.get("mpn")

            images = prod.get("image")
            if isinstance(images, list):
                product.images = images
            elif isinstance(images, str):
                product.images = images

            offers = prod.get("offers") or {}
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if isinstance(offers, dict):
                product.price = _safe_float(offers.get("price"))
                product.stock = 0

        left_col = soup.select_one(".content-frame .col-xs-24.col-md-14")
        right_col = soup.select_one(".content-frame .col-xs-24.col-md-10")

        if left_col:
            product.description_left = " ".join(left_col.stripped_strings)
            if product.description_left:
                product.description_left = _translate_en_ru(product.description_left)

        if right_col:
            product.description_right = " ".join(right_col.stripped_strings)
            if product.description_right:
                product.description_right = _translate_en_ru(product.description_right)

        if product.category_path:
            product.category_path = [_translate_en_ru(c) for c in product.category_path]

        if not product.name:
            h1 = soup.find(["h1", "h2"], attrs={"itemprop": "name"}) or soup.find("h1")
            product.name = h1.get_text(strip=True) if h1 else product.name

        if product.price is None:
            price_el = soup.select_one("[itemprop='price'], meta[itemprop='price']")
            if price_el:
                val = price_el.get("content") or price_el.get_text(strip=True)
                product.price = _safe_float(val)
        return product

    @staticmethod
    def _extract_jsonld_objects(soup: BeautifulSoup) -> list[dict]:
        result = []
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
                if isinstance(data, list):
                    result.extend(data)
                elif isinstance(data, dict):
                    result.append(data)
            except Exception:
                continue
        return result

    @staticmethod
    def _find_first_by_type(objs: list[dict], type_name: str) -> dict | None:
        for obj in objs:
            t = obj.get("@type")
            if isinstance(t, list):
                if type_name in t:
                    return obj
            elif isinstance(t, str):
                if t.lower() == type_name.lower():
                    return obj
        return None

    @staticmethod
    def _extract_breadcrumbs(objs: list[dict]) -> list[str] | None:  # noqa: C901
        bl = None
        for obj in objs:
            t = obj.get("@type")
            if (isinstance(t, str) and t.lower() == "breadcrumblist") or (
                isinstance(t, list) and "BreadcrumbList" in t
            ):
                bl = obj
                break
        if not bl:
            return None
        items = bl.get("itemListElement") or []
        names = []
        for it in items:
            if isinstance(it, dict):
                elt = it.get("item") or {}
                if isinstance(elt, dict):
                    name = elt.get("name")
                else:
                    name = it.get("name")
                if name:
                    names.append(str(name).strip())
        return names or None

    @staticmethod
    def _extract_breadcrumbs_from_dom(soup: BeautifulSoup) -> list[str] | None:
        trail = []
        for li in soup.select(
            "nav.breadcrumbs li, ol.breadcrumb li, nav[aria-label*=breadcrumb] li"
        ):
            txt = li.get_text(" ", strip=True)
            if txt:
                trail.append(txt)
        return trail or None


def _safe_float(x) -> float | None:
    try:
        if x is None:
            return None
        return float(str(x).strip().replace(",", "."))
    except Exception:
        return None


def is_russian_text(text: str) -> bool:
    if not text or len(text) < 10:
        return False
    cyrillic_chars = sum(1 for c in text if "\u0400" <= c <= "\u04FF")
    russian_ratio = cyrillic_chars / len(text)
    return russian_ratio > 0.3


def safe_translate_if_english(text: str, _translator=None) -> str:
    if not text:
        return ""
    if is_russian_text(text):
        return text
    return _translate_en_ru(text[:1000])


def crawl(  # noqa: C901
    scraper: IHerbScraper, start_url: str, max_pages: int, limit: int
) -> list[ProductScraper]:
    products: list[ProductScraper] = []
    seen_urls = set()

    for page_url in scraper.iter_listing_pages(start_url, max_pages=max_pages):
        try:
            html = scraper.get(page_url).text
        except requests.HTTPError:
            continue

        links = scraper.extract_product_links(html, page_url)
        for link in links:
            if link in seen_urls:
                continue
            seen_urls.add(link)
            try:
                prod = scraper.parse_product_page(link)
                if prod:
                    products.append(prod)
                    if limit and len(products) >= limit:
                        return products
            except Exception:
                continue

    return products


def main():
    ap = argparse.ArgumentParser(description="Скрапер по url с iherb.com")
    args = ap.parse_args()

    if args.query:
        start_url = IHerbScraper.build_search_url(args.query, page=1)
    else:
        start_url = args.start_url
        if not start_url.startswith("http"):
            start_url = urljoin(BASE, start_url)

    scraper = IHerbScraper()
    crawl(scraper, start_url=start_url, max_pages=args.max_pages, limit=args.limit)


if __name__ == "__main__":
    main()
