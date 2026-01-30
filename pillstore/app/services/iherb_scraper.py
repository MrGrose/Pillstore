from __future__ import annotations
import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin, urlencode, urlparse, parse_qs, urlunparse
import cloudscraper
from googletrans import Translator

import requests
from bs4 import BeautifulSoup
import random

translator = Translator()
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

@dataclass
class Product:
    name: str| None = None
    name_en: str| None = None
    brand: str| None = None
    mpn: str| None = None
    price: float| None = None
    stock: int | None = 5
    url: str | None = None
    images: str | None = None
    category_path: list[str]| None = None
    description_left: str | None = None
    description_right: str | None = None


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
    
    cyrillic_chars = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    russian_ratio = cyrillic_chars / len(text)
    
    return russian_ratio > 0.3

def safe_translate_if_english(text: str, translator) -> str:
    if not text:
        return ""
    
    if is_russian_text(text):
        return text
    
    try:
        translated = translator.translate(text[:1000], src='en', dest='ru')
        return translated.text
    except Exception as e:
        return text

class IHerbScraper:
    def __init__(self, session: requests.Session | None = None):
        self.sess = session or cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.sess.headers.update(HEADERS)
        self.sess.cookies.set("iher-pref1", "en-US")
        self.sess.cookies.set("iher-pref2", "US")

    def _normalize_www(self, url: str) -> str:
        pu = urlparse(url)
        if pu.netloc.startswith("de.iherb.com"):
            pu = pu._replace(netloc="www.iherb.com")
        return urlunparse(pu)

    def get(self, url: str):
        url = self._normalize_www(url)
        if not hasattr(self, '_ua_counter'):
            self._ua_counter = 0
        self._ua_counter += 1
        if self._ua_counter % 5 == 0:
            self.sess.headers['User-Agent'] = random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ])
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if "/search" in url or "/c/" in url:
                    self.sess.headers["Referer"] = "https://www.iherb.com/"
                
                resp = self.sess.get(url, timeout=(10, 60), allow_redirects=True)
                if resp.status_code == 403:
                    raise requests.HTTPError(f"403 Forbidden for {url}")
                resp.raise_for_status()
                
                time.sleep(random.uniform(3, 6))
                return resp
                
            except requests.exceptions.ReadTimeout:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    print(f"[RETRY {attempt+1}/{max_retries}] {url} (ждём {wait:.1f}s)")
                    time.sleep(wait)
                    continue
                print(f"[FAIL] {url} после {max_retries} попыток")
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

    def extract_product_links(self, listing_html: str, base_url: str) -> List[str]:
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


    def parse_product_page(self, url: str) -> Product | None:
        try:
            html = self.get(url).text
        except requests.HTTPError:
            return None

        soup = BeautifulSoup(html, "lxml")
        product = Product(url=self._normalize_www(url))

        data = self._extract_jsonld_objects(soup)
        product.category_path = self._extract_breadcrumbs(data) or self._extract_breadcrumbs_from_dom(soup)

        prod = self._find_first_by_type(data, "Product")
        if prod:
            product.name_en = prod.get("name") or product.name_en
            if product.name_en:
                try:
                    translated = translator.translate(product.name_en, src='en', dest='ru')
                    product.name = translated.text
                except Exception as e:
                    print(f"[WARN] NAME RU: {e}")
                    
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
                
                
        left_col = soup.select_one('.content-frame .col-xs-24.col-md-14')
        right_col = soup.select_one('.content-frame .col-xs-24.col-md-10')
        
        if left_col:
            product.description_left = ' '.join(left_col.stripped_strings)
            if product.description_left:
                try:
                    translated = translator.translate(product.description_left, src='en', dest='ru')
                    product.description_left = translated.text
                except Exception as e:
                    print(f"[WARN] Left translation: {e}")

        if right_col:
            product.description_right = ' '.join(right_col.stripped_strings)
            if product.description_right:
                try:
                    translated = translator.translate(product.description_right, src='en', dest='ru')
                    product.description_right = translated.text
                except Exception as e:
                    print(f"[WARN] Right translation: {e}")
        
        if product.category_path:
            translated_path = []
            for cat_name in product.category_path:
                try:
                    translated = translator.translate(cat_name, src='en', dest='ru')
                    translated_path.append(translated.text)
                except Exception as e:
                    translated_path.append(cat_name)
            product.category_path = translated_path
            
        if not product.name:
            h1 = soup.find(["h1", "h2"], attrs={"itemprop": "name"}) or soup.find("h1")
            product.name = h1.get_text(strip=True) if h1 else product.name

        if product.price is None:
            price_el = soup.select_one('[itemprop="price"], meta[itemprop="price"]')
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
    def _extract_breadcrumbs(objs: list[dict]) -> list[str] | None:
        bl = None
        for obj in objs:
            t = obj.get("@type")
            if (isinstance(t, str) and t.lower() == "breadcrumblist") or (isinstance(t, list) and "BreadcrumbList" in t):
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
        for li in soup.select("nav.breadcrumbs li, ol.breadcrumb li, nav[aria-label*=breadcrumb] li"):
            txt = li.get_text(" ", strip=True)
            if txt:
                trail.append(txt)
        return trail or None


def save_csv(products: list[Product], path: Path):
    fieldnames = list(asdict(products[0]).keys()) if products else [f.name for f in Product.__dataclass_fields__.values()]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for p in products:
            row = asdict(p)
            if isinstance(row.get("images"), list):
                row["images"] = " | ".join(row["images"])
            if isinstance(row.get("category_path"), list):
                row["category_path"] = " > ".join(row["category_path"])
            w.writerow(row)


def save_json(products: list[Product], path: Path):
    with path.open("w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in products], f, ensure_ascii=False, indent=2)


def save_jsonl(products: list[Product], path: Path):
    with path.open("w", encoding="utf-8") as f:
        for p in products:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")



def crawl(scraper: IHerbScraper, start_url: str, max_pages: int, limit: int, out_path: Path) -> list[Product]:
    products: list[Product] = []
    seen_urls = set()
    out_path.parent.mkdir(parents=True, exist_ok=True) 
    out_path.write_text('[]')
    
    for page_url in scraper.iter_listing_pages(start_url, max_pages=max_pages):
        try:
            html = scraper.get(page_url).text
        except requests.HTTPError as e:
            print(f"[WARN] listing fetch failed {page_url}: {e}", file=sys.stderr)
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
                    
                    current_data = []
                    if out_path.exists():
                        current_data = json.loads(out_path.read_text())
                    current_data.append(asdict(prod))
                    with out_path.open('w', encoding='utf-8') as f:
                        json.dump(current_data, f, ensure_ascii=False, indent=2)
                    
                    print(f"[OK] {prod.name or '(no name)'} — {prod.price} | {link}")
                    
                    if limit and len(products) >= limit:
                        return products
                else:
                    print(f"[SKIP] failed to parse {link}", file=sys.stderr)
            except Exception as e:
                print(f"[ERROR] {link}: {e}", file=sys.stderr)
                continue

    return products


def main():
    ap = argparse.ArgumentParser(description="Scrape products from www.iherb.com (USD)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--query", help="Поисковый запрос (kw)")
    g.add_argument("--start-url", help="Стартовая страница (каталог/поиск/фильтр)")
    ap.add_argument("--max-pages", type=int, default=3, help="Максимум страниц листинга для обхода")
    ap.add_argument("--limit", type=int, default=None, help="Ограничить число товаров")
    ap.add_argument("--out", required=True, help="Путь к JSON файлу")
    args = ap.parse_args()
    
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    if args.query:
        start_url = IHerbScraper.build_search_url(args.query, page=1)
    else:
        start_url = args.start_url
        if not start_url.startswith("http"):
            start_url = urljoin(BASE, start_url)

    pu = urlparse(start_url)
    if pu.netloc.startswith("de.iherb.com"):
        pu = pu._replace(netloc="www.iherb.com")
    start_url = urlunparse(pu)

    scraper = IHerbScraper()
    
    crawl(scraper, start_url=start_url, max_pages=args.max_pages, 
                     limit=args.limit, out_path=out_path)
    
if __name__ == "__main__":
    main()
