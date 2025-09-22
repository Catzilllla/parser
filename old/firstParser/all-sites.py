#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Боевой парсер поиска по списку сайтов + конкретные реализации для Citilink и KartridgMSK.
Python 3.12
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import urllib.parse
from typing import Optional, Tuple

# --- Настройки поиска ---
SITES = [
    {"name": "XCOM", "url": "https://www.xcom-shop.ru/", "method": "api"},
    {"name": "YandexBusiness", "url": "https://business.market.yandex.ru/", "method": "api"},
    {"name": "Regard", "url": "https://www.regard.ru/", "method": "api"},
    {"name": "Citilink", "url": "https://www.citilink.ru", "method": "api"},
    {"name": "ZipRe", "url": "https://zip.re/", "method": "api"},
    {"name": "Shesternya", "url": "http://shesternya-zip.ru/", "method": "html"},
    {"name": "Pantum", "url": "https://pantum-shop.ru/", "method": "api"},
    {"name": "KNS", "url": "https://www.kns.ru/", "method": "html"},
    {"name": "InkMarket", "url": "https://ink-market.ru/", "method": "api"},
    {"name": "PrintCorner", "url": "https://www.printcorner.ru/", "method": "api"},
    {"name": "Cartridge", "url": "https://cartridge.ru/", "method": "api"},
    {"name": "Opticart", "url": "https://opticart.ru/", "method": "api"},
    {"name": "Lazerka", "url": "https://www.lazerka.net/", "method": "api"},
    {"name": "Imprints", "url": "https://imprints.ru/", "method": "html"},
    {"name": "KartridgMSK", "url": "https://kartridgmsk.ru/", "method": "api"},
]

QUERIES = [
    "Шлейф панели Sharp QCNW-0208FCZZ",
    "RM1-1740-040CN",
]

# Заголовки для requests
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Referer": "https://www.google.com/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
}

# Опционально можно добавить cookies
COOKIES = {}

# Таймауты и паузы
REQUEST_TIMEOUT = 12
SLEEP_BETWEEN_REQUESTS = 0.8
MAX_RETRIES = 2
RETRY_BACKOFF = 1.5

# --- Регулярки для цен ---
money_re = re.compile(
    r"(?:\d{1,3}(?:[ \u00A0]?\d{3})*(?:[.,]\d+)?)[ \u00A0]*[₽р]"
    r"|(?:\d+[.,]?\d*)\s*(?:руб\.?|р\.?)",
    re.I,
)
digits_re = re.compile(r"[\d \u00A0]+[,\.]?\d*")

def extract_price_from_text(text: str) -> Optional[str]:
    """Попытаться найти цену в тексте (первое соответствие)."""
    if not text:
        return None
    m = money_re.search(text)
    if m:
        return m.group(0).strip()
    m2 = re.search(r"(\d[\d \u00A0,\.]*?)\s*(руб|руб\.)", text, re.I)
    if m2:
        return f"{m2.group(1).strip()} руб."
    m3 = digits_re.search(text)
    if m3:
        return m3.group(0).strip()
    return None

def safe_get(session: requests.Session, url: str, params=None, headers=None, allow_redirects=True) -> Optional[requests.Response]:
    """GET с ретраями и обработкой ошибок."""
    tries = 0
    while tries <= MAX_RETRIES:
        try:
            r = session.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=allow_redirects)
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            print(f"[HTTP ERR] {url} → {e} (status: {getattr(e.response, 'status_code', None)})")
            if 500 <= getattr(e.response, "status_code", 0) < 600 and tries < MAX_RETRIES:
                tries += 1
                time.sleep(RETRY_BACKOFF ** tries)
                continue
            return None
        except requests.RequestException as e:
            print(f"[REQ ERR] {url} → {e}")
            tries += 1
            time.sleep(RETRY_BACKOFF ** tries)
    return None

# --- Сайт-специфичные парсеры ---
def parse_citilink(session: requests.Session, query: str) -> Optional[Tuple[str, str]]:
    base = "https://www.citilink.ru/search/"
    params = {"text": query}
    r = safe_get(session, base, params=params, headers=COMMON_HEADERS)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    candidates = soup.select("a.ProductCardHorizontal__title, a.ProductCardVertical__title, a.ProductCard__title, a.product-card__name")
    if not candidates:
        candidates = soup.find_all("a", href=True)
    qlow = query.lower()
    for a in candidates:
        title = a.get_text(" ", strip=True)
        if title and qlow in title.lower():
            parent = a.find_parent()
            price = extract_price_from_text(parent.get_text(" ", strip=True)) if parent else None
            if not price:
                price = extract_price_from_text(soup.get_text(" ", strip=True))
            return (title, price or "Цена не найдена")
    return None

def parse_kartridgmsk(session: requests.Session, query: str) -> Optional[Tuple[str, str]]:
    qenc = urllib.parse.quote_plus(query)
    tried_urls = [
        f"https://kartridgmsk.ru/?s={qenc}",
        f"https://kartridgmsk.ru/?search={qenc}",
        f"https://kartridgmsk.ru/catalog/?q={qenc}",
        f"https://kartridgmsk.ru/index.php?route=product/search&filter_name={qenc}",
    ]
    for url in tried_urls:
        r = safe_get(session, url, headers=COMMON_HEADERS)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("div.product, div.item, div.catalog-item, li.product, a.product-name")
        if not items:
            items = soup.find_all("a", href=True)
        qlow = query.lower()
        for it in items:
            title = it.get_text(" ", strip=True)
            if title and qlow in title.lower():
                parent = it.find_parent()
                price = extract_price_from_text(parent.get_text(" ", strip=True)) if parent else None
                if not price:
                    price = extract_price_from_text(soup.get_text(" ", strip=True))
                return (title, price or "Цена не найдена")
        time.sleep(0.25)
    return None

def parse_generic_html(session: requests.Session, site: dict, query: str) -> Optional[Tuple[str, str]]:
    base = site["url"].rstrip("/")
    candidates_urls = [
        f"{base}/search/?q={urllib.parse.quote_plus(query)}",
        f"{base}/search/?text={urllib.parse.quote_plus(query)}",
        f"{base}/search/?s={urllib.parse.quote_plus(query)}",
        f"{base}/?s={urllib.parse.quote_plus(query)}",
    ]
    for url in candidates_urls:
        r = safe_get(session, url, headers=COMMON_HEADERS)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        elems = soup.select("div.product, div.item, li.product, div.catalog-item, div.card, article")
        if not elems:
            elems = soup.find_all(["a", "div", "li"])
        qlow = query.lower()
        for e in elems:
            title = e.get_text(" ", strip=True)
            if title and qlow in title.lower():
                price = extract_price_from_text(e.get_text(" ", strip=True)) or extract_price_from_text(soup.get_text(" ", strip=True))
                return (title.strip(), price or "Цена не найдена")
        time.sleep(0.2)
    return None

# --- Router для сайтов ---
def search_site(session: requests.Session, site: dict, query: str) -> Optional[Tuple[str, str]]:
    try:
        if "citilink" in site["url"]:
            return parse_citilink(session, query)
        if "kartridgmsk" in site["url"]:
            return parse_kartridgmsk(session, query)
        return parse_generic_html(session, site, query)
    except Exception as e:
        print(f"[PARSE ERR] {site.get('name')} → {e}")
        return None

# --- Main ---
def main():
    session = requests.Session()
    session.headers.update(COMMON_HEADERS)
    if COOKIES:
        session.cookies.update(COOKIES)

    for query in QUERIES:
        print(f"\n=== Поиск: {query} ===")
        for site in SITES:
            name = site.get("name") or site.get("url")
            try:
                res = search_site(session, site, query)
                if res:
                    title, price = res
                    print(f"[{name}] → ({title}) : {price}")
                else:
                    print(f"[{name}] → не найдено")
            except Exception as e:
                print(f"[{name}] → Ошибка: {e}")
            time.sleep(SLEEP_BETWEEN_REQUESTS)

if __name__ == "__main__":
    main()
