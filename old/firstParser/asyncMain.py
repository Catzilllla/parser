#!/usr/bin/env python3
"""
price_scraper_async.py

Асинхронный скрипт для поиска рыночных цен (в руб.)
по списку позиций из CSV (source.csv).

Источники:
- chipdip.ru
- laserparts.ru
- tze1.ru
- zipzip.ru

Особенности:
- Использует aiohttp + asyncio для параллельных запросов.
- Ограничивает одновременные запросы (Semaphore).
- Кэширует результаты по позициям.
- Сохраняет промежуточные результаты каждые N записей.
"""

import sys
import csv
import re
import asyncio
import aiohttp
import urllib.parse
from typing import Optional, Tuple, List, Dict

# ----------------- Конфигурация ---------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                  " (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}
REQUEST_TIMEOUT = 10
MAX_CONCURRENT_REQUESTS = 10  # ограничение параллельных запросов
SAVE_EVERY = 500              # каждые N результатов сохранять промежуточный CSV

SITES = ["chipdip", "laserparts", "tze1", "zipzip"]

PRICE_RE = re.compile(r"(\d[\d\s]*[,\.]?\d*)\s*(?:руб\.?|₽|RUB)", re.I)
NUM_RE = re.compile(r"(\d[\d\s]*[,\.]?\d*)")

CACHE: Dict[str, Tuple[Optional[float], Optional[str], Optional[str]]] = {}

sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# ----------------- Парсинг цены ---------------------

def parse_price_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    m = PRICE_RE.search(text)
    if m:
        raw = m.group(1)
    else:
        m2 = NUM_RE.search(text)
        if not m2:
            return None
        raw = m2.group(1)
    cleaned = raw.replace(' ', '').replace('\xa0', '').replace(',', '.')
    try:
        return float(cleaned)
    except Exception:
        return None

# ----------------- Запросы --------------------------

async def fetch(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    try:
        async with sem:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status == 200:
                    return await resp.text()
    except Exception:
        return None
    return None

# ----------------- Парсеры сайтов -------------------

async def search_chipdip(session, query: str):
    q = urllib.parse.quote_plus(query)
    url = f"https://www.chipdip.ru/search/?q={q}"
    html = await fetch(session, url)
    if not html:
        return None, None
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    item = soup.select_one('.catalog-item, .product-card, .search-result__item')
    if not item:
        price = parse_price_from_text(soup.get_text(' ', strip=True))
        return price, url if price else (None, None)
    price = parse_price_from_text(item.get_text(' ', strip=True))
    link = item.select_one('a')
    href = urllib.parse.urljoin('https://www.chipdip.ru', link.get('href')) if link and link.get('href') else url
    return price, href if price else (None, href)

async def search_laserparts(session, query: str):
    q = urllib.parse.quote_plus(query)
    url = f"https://laserparts.ru/search/?q={q}"
    html = await fetch(session, url)
    if not html:
        return None, None
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    item = soup.select_one('.product-card, .catalog-item, .product')
    if item:
        price = parse_price_from_text(item.get_text(' ', strip=True))
        link = item.select_one('a')
        href = urllib.parse.urljoin('https://laserparts.ru', link.get('href')) if link and link.get('href') else url
        return price, href if price else (None, href)
    price = parse_price_from_text(soup.get_text(' ', strip=True))
    return price, url if price else (None, None)

async def search_tze1(session, query: str):
    q = urllib.parse.quote_plus(query)
    url = f"https://tze1.ru/?s={q}"
    html = await fetch(session, url)
    if not html:
        return None, None
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    item = soup.select_one('.product, .item, .search-result')
    if item:
        price = parse_price_from_text(item.get_text(' ', strip=True))
        link = item.select_one('a')
        href = urllib.parse.urljoin('https://tze1.ru', link.get('href')) if link and link.get('href') else url
        return price, href if price else (None, href)
    price = parse_price_from_text(soup.get_text(' ', strip=True))
    return price, url if price else (None, None)

async def search_zipzip(session, query: str):
    q = urllib.parse.quote_plus(query)
    url = f"https://zipzip.ru/search/?q={q}"
    html = await fetch(session, url)
    if not html:
        return None, None
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    item = soup.select_one('.product, .catalog-item, .product-card')
    if item:
        price = parse_price_from_text(item.get_text(' ', strip=True))
        link = item.select_one('a')
        href = urllib.parse.urljoin('https://zipzip.ru', link.get('href')) if link and link.get('href') else url
        return price, href if price else (None, href)
    price = parse_price_from_text(soup.get_text(' ', strip=True))
    return price, url if price else (None, None)

SEARCH_FUNCS = {
    'chipdip': search_chipdip,
    'laserparts': search_laserparts,
    'tze1': search_tze1,
    'zipzip': search_zipzip,
}

# ----------------- Основная логика ------------------

async def find_price_for_item(session, item: str):
    if item in CACHE:
        return CACHE[item]
    for site in SITES:
        func = SEARCH_FUNCS[site]
        try:
            price, url = await func(session, item)
        except Exception:
            price, url = None, None
        if price is not None:
            result = (price, site, url)
            CACHE[item] = result
            return result
    CACHE[item] = (None, None, None)
    return None, None, None

async def process_items(infile: str, outfile: str):
    items = []
    with open(infile, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                items.append(row[0].strip())

    results = []
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for idx, item in enumerate(items, 1):
            price, site, url = await find_price_for_item(session, item)
            if price is None:
                print(f"[{idx}/{len(items)}] {item} → не найдено")
                results.append((item, '', '', ''))
            else:
                print(f"[{idx}/{len(items)}] {item} → {price:.2f} руб. ({site})")
                results.append((item, f"{price:.2f}", site, url))

            if idx % SAVE_EVERY == 0:
                with open(outfile, 'w', newline='', encoding='utf-8') as csvf:
                    writer = csv.writer(csvf)
                    writer.writerow(['item', 'price_rub', 'source_site', 'source_url'])
                    writer.writerows(results)
                print(f"--- Сохранено промежуточно: {idx} строк")

    with open(outfile, 'w', newline='', encoding='utf-8') as csvf:
        writer = csv.writer(csvf)
        writer.writerow(['item', 'price_rub', 'source_site', 'source_url'])
        writer.writerows(results)
    print(f"Готово — результаты записаны в {outfile}")

# ----------------- Точка входа ----------------------

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Использование: python3 price_scraper_async.py source.csv output.csv")
        sys.exit(1)
    infile = sys.argv[1]
    outfile = sys.argv[2]
    asyncio.run(process_items(infile, outfile))
