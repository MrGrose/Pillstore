from __future__ import annotations

import argparse
import json
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

from app.utils.description_parser import (
    _strip_disclaimer as _strip_iherb_translation_disclaimer,
    split_right_column_text,
    split_text_by_section_headers,
)


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
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.iherb.com/",
}

REQUEST_TIMEOUT = 45
SLEEP_BETWEEN_REQUESTS = (2.0, 4.0)

SKIP_DETAILS_SECTIONS = {"Отказ от ответственности", "Производитель"}


def _parse_overview_section(overview_block) -> list[dict]:
    sections = []
    direct_divs = overview_block.find_all("div", recursive=False)
    with_h3 = [d for d in direct_divs if d.select_one("h3")]
    if with_h3:
        for block in with_h3:
            h3 = block.select_one("h3")
            if not h3:
                continue
            title = h3.get_text(strip=True)
            if title in SKIP_DETAILS_SECTIONS:
                continue
            content_div = block.select_one("div")
            if not content_div:
                content_div = block
            items = []
            for li in content_div.select("ul li"):
                t = li.get_text(separator=" ", strip=True)
                if t:
                    items.append(t)
            for p in content_div.select("p"):
                t = p.get_text(separator=" ", strip=True)
                if t:
                    items.append(_strip_iherb_translation_disclaimer(t))
            if not items:
                text = content_div.get_text(separator=" ", strip=True)
                if text:
                    items = [_strip_iherb_translation_disclaimer(text)]
            if items:
                sections.append({"title": title, "content": items})
        if sections:
            return sections
    div = overview_block.select_one("div") or overview_block
    full_text = div.get_text(separator="\n", strip=True)
    parsed = split_text_by_section_headers(full_text)
    if parsed:
        return parsed
    items = []
    for li in div.select("ul li"):
        t = li.get_text(separator=" ", strip=True)
        if t:
            items.append(t)
    for p in div.select("p"):
        t = p.get_text(separator=" ", strip=True)
        if t:
            items.append(_strip_iherb_translation_disclaimer(t))
    if items:
        sections.append({"title": "О продукте", "content": items})
    return sections


def _parse_details_sections(details_block) -> list[dict]:
    sections = []
    for block in details_block.select(":scope > div"):
        if block.get("class") and "overview-link-wrapper" in block.get("class", []):
            continue
        h3 = block.select_one("h3")
        if not h3:
            continue
        title = h3.get_text(strip=True)
        if title in SKIP_DETAILS_SECTIONS:
            continue
        content_div = block.select_one("div")
        if not content_div:
            continue
        paras = [p.get_text(separator=" ", strip=True) for p in content_div.select("p") if p.get_text(strip=True)]
        if not paras:
            text = content_div.get_text(separator=" ", strip=True)
            if text:
                paras = [_strip_iherb_translation_disclaimer(text)]
        else:
            paras = [_strip_iherb_translation_disclaimer(p) for p in paras]
        if paras:
            sections.append({"title": title, "content": paras})
    return sections


def _parse_supplement_sections(supplement_block) -> list[dict]:
    sections = []
    table = supplement_block.select_one(".supplement-facts-container table")
    if table:
        rows = []
        for tr in table.select("tr"):
            row_text = tr.get_text(separator=" ", strip=True)
            if row_text:
                rows.append(row_text.replace("† †", "†"))
        if rows:
            sections.append({"title": "Информация о добавке", "content": rows})
    for block in supplement_block.select(":scope > div"):
        if block.select_one(".supplement-facts-container"):
            continue
        h3 = block.select_one("h3")
        if not h3:
            continue
        title = h3.get_text(strip=True)
        content_div = block.select_one("div")
        if not content_div:
            continue
        paras = [p.get_text(separator=" ", strip=True) for p in content_div.select("p") if p.get_text(strip=True)]
        if not paras:
            text = content_div.get_text(separator=" ", strip=True)
            if text:
                paras = [text]
        if paras:
            sections.append({"title": title, "content": paras})
    return sections


def _build_structured_description(
    soup, overview_block, details_block, supplement_block
) -> tuple[str | None, str | None]:
    left_sections = []
    if overview_block:
        left_sections.extend(_parse_overview_section(overview_block))
    if details_block:
        left_sections.extend(_parse_details_sections(details_block))
    right_sections = _parse_supplement_sections(supplement_block) if supplement_block else []
    left_json = json.dumps(left_sections, ensure_ascii=False) if left_sections else None
    right_json = json.dumps(right_sections, ensure_ascii=False) if right_sections else None
    return left_json, right_json


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
        self.sess.cookies.set("iher-pref1", "ru-RU")
        self.sess.cookies.set("iher-pref2", "RU")

    def _normalize_www(self, url: str) -> str:
        pu = urlparse(url)
        if pu.netloc.startswith("de.iherb.com"):
            pu = pu._replace(netloc="www.iherb.com")
        return urlunparse(pu)

    def _product_url_for_rubles(self, url: str) -> str:
        pu = urlparse(url)
        path = (pu.path or "").strip().lower()
        if path.startswith("/pr/") and "iherb.com" in pu.netloc and "ru.iherb.com" not in pu.netloc:
            pu = pu._replace(netloc="ru.iherb.com")
            return urlunparse(pu)
        return url

    def _is_cloudflare_challenge(self, resp: requests.Response) -> bool:
        if resp.status_code in (403, 503):
            return True
        text = (resp.text or "").lower()
        return (
            "just a moment" in text
            or "cf-browser-verification" in text
            or "checking your browser" in text
        )

    def _fetch_via_playwright(self, url: str, wait_selector: str | None = None) -> str | None:
        if not PLAYWRIGHT_AVAILABLE or sync_playwright is None:
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                context = browser.new_context(
                    locale="ru-RU",
                    user_agent=HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"},
                )
                context.add_cookies([
                    {"name": "iher-pref1", "value": "ru-RU", "domain": ".iherb.com", "path": "/"},
                    {"name": "iher-pref2", "value": "RU", "domain": ".iherb.com", "path": "/"},
                ])
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=15000)
                else:
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    page.wait_for_timeout(5000)
                html = page.content()
                browser.close()
                return html
        except Exception:
            return None

    def get(self, url: str):  # noqa: C901
        url = self._normalize_www(url)
        url = self._product_url_for_rubles(url)
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
        except requests.HTTPError:
            return None

        try:
            product = self._parse_product_page_html(url, html)
            if not product.description_right and product.description_left and PLAYWRIGHT_AVAILABLE:
                fetch_url = self._normalize_www(url)
                fetch_url = self._product_url_for_rubles(fetch_url)
                html2 = _playwright_executor.submit(
                    self._fetch_via_playwright,
                    fetch_url,
                    None,
                ).result(timeout=70)
                if html2:
                    product = self._parse_product_page_html(url, html2)
            return product
        except Exception:
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
                product.stock = 0
                raw_ld = offers.get("price")
                p_ld = _safe_float(raw_ld)
                if p_ld is not None:
                    product.price = p_ld

            desc_ld = prod.get("description")
            if isinstance(desc_ld, str) and desc_ld.strip():
                product.description_left = _strip_iherb_translation_disclaimer(
                    _translate_en_ru(desc_ld.strip())
                )

        overview_block = soup.select_one("#overview .overview-info")
        details_block = soup.select_one("#details .details-info")
        supplement_block = soup.select_one("#product-supplement-facts .ingredient-info")
        if overview_block or details_block or supplement_block:
            left_json, right_json = _build_structured_description(
                soup, overview_block, details_block, supplement_block
            )
            if left_json:
                product.description_left = left_json
            if right_json:
                product.description_right = right_json
        else:
            overview = soup.select_one("#product-overview .content-frame, .product-overview .content-frame")
            if not overview:
                overview = soup.select_one(".content-wrapper .content-frame")
            if not overview:
                for frame in soup.select(".content-frame"):
                    if frame.select_one(".col-xs-24.col-md-14") and frame.select_one(".col-xs-24.col-md-10"):
                        overview = frame
                        break
            if not overview:
                row = soup.select_one(".row .col-xs-24.col-md-14")
                if row:
                    row = row.find_parent(class_=lambda c: c and "row" in str(c))
                    if row and row.select_one(".col-xs-24.col-md-10"):
                        overview = row
            left_col = overview.select_one(".col-xs-24.col-md-14") if overview else None
            right_col = overview.select_one(".col-xs-24.col-md-10") if overview else None
            if left_col:
                dom_left = left_col.get_text(separator="\n", strip=True)
                if dom_left:
                    translated = _translate_en_ru(dom_left)
                    left_sections = split_text_by_section_headers(translated)
                    if not left_sections:
                        left_sections = [{"title": "Описание", "content": [_strip_iherb_translation_disclaimer(translated)]}]
                    product.description_left = json.dumps(left_sections, ensure_ascii=False)
            if right_col:
                dom_right = right_col.get_text(separator="\n", strip=True)
                if dom_right:
                    translated = _translate_en_ru(dom_right)
                    right_sections = split_right_column_text(translated)
                    if not right_sections:
                        right_sections = [{"title": "Пищевая ценность", "content": [translated]}]
                    product.description_right = json.dumps(right_sections, ensure_ascii=False)

        if product.category_path:
            product.category_path = [_translate_en_ru(c) for c in product.category_path]

        if not product.name:
            h1 = soup.find(["h1", "h2"], attrs={"itemprop": "name"}) or soup.find("h1")
            product.name = h1.get_text(strip=True) if h1 else product.name

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


def _normalize_price_string(s: str) -> str:
    s = re.sub(r"[\s₽$€]", "", str(s).strip())
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return s


def _safe_float(x) -> float | None:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        s = _normalize_price_string(s)
        return float(s)
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
