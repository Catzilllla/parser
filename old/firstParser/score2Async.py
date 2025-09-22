import asyncio
import aiohttp
import csv
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import sys
import os
import logging
from tqdm import tqdm
import re

# ----------- Настройки -----------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive"
}
BATCH_SIZE = 100
SAVE_EVERY = 500
TIMEOUT = 20
SEM_LIMIT = 10
LOG_FILE = "errors.log"
# ---------------------------------

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

sem = asyncio.Semaphore(SEM_LIMIT)


def normalize(s: str) -> str:
    return s.lower().replace("-", "").replace(" ", "")


def match_score(q: str, f: str) -> int:
    if not f:
        return 0
    return fuzz.ratio(normalize(q), normalize(f))


def extract_article(text: str) -> str:
    """Извлекает артикул (последовательность букв+цифр от 6 символов)"""
    match = re.search(r"[A-Za-z0-9]{6,}", text)
    return match.group(0) if match else ""


# ---------- HTTP ----------
async def fetch(session: aiohttp.ClientSession, url: str, is_json=False):
    async with sem:
        try:
            async with session.get(url, timeout=TIMEOUT) as resp:
                if resp.status == 200:
                    if is_json:
                        return await resp.json(content_type=None)
                    return await resp.text()
                else:
                    logging.warning(f"Ошибка {resp.status} при запросе {url}")
        except Exception as e:
            logging.warning(f"Ошибка запроса {url}: {e}")
            return None
    return None
# --------------------------


# ---------- Chipdip API ----------
async def search_chipdip_api(session, item: str):
    url = f"https://www.chipdip.ru/ajaxsearch?searchtext={item}"
    data = await fetch(session, url, is_json=True)
    if not data or "items" not in data or not data["items"]:
        return None

    article = extract_article(item)
    best = None
    best_score = 0

    for prod in data["items"]:
        found_name = prod.get("Name", "").strip()
        prod_url = "https://www.chipdip.ru" + prod.get("Url", "")
        try:
            price_val = float(str(prod.get("Price", "0")).replace(",", "."))
        except Exception:
            continue

        if article and article.lower() in found_name.lower():
            return price_val, "chipdip.ru", prod_url, found_name

        score = match_score(item, found_name)
        if score > best_score:
            best_score = score
            best = (price_val, "chipdip.ru", prod_url, found_name)

    return best
# ---------------------------------


# ---------- Общая логика для HTML сайтов ----------
def pick_best_product(products, item: str, site: str, base_url: str):
    article = extract_article(item)
    best = None
    best_score = 0

    for name, price, url in products:
        if not name or not price:
            continue

        if article and article.lower() in name.lower():
            return price, site, url, name

        score = match_score(item, name)
        if score > best_score:
            best_score = score
            best = (price, site, url, name)

    return best
# ---------------------------------


# ---------- Остальные сайты ----------
async def search_laserparts(session, item: str):
    url = f"https://www.laserparts.ru/search?query={item}"
    html = await fetch(session, url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for prod in soup.select(".product-item"):
        name = prod.select_one(".product-title")
        price = prod.select_one(".price")
        if name and price:
            try:
                price_val = float(price.text.strip().split()[0].replace(",", "."))
            except Exception:
                continue
            products.append((name.text.strip(), price_val, url))
    return pick_best_product(products, item, "laserparts.ru", url)


async def search_tze1(session, item: str):
    url = f"https://tze1.ru/search?search={item}"
    html = await fetch(session, url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for prod in soup.select(".product-thumb"):
        name = prod.select_one(".caption a")
        price = prod.select_one(".price")
        if name and price:
            try:
                price_val = float(price.text.strip().split()[0].replace(",", "."))
            except Exception:
                continue
            products.append((name.text.strip(), price_val, url))
    return pick_best_product(products, item, "tze1.ru", url)


async def search_zipzip(session, item: str):
    url = f"https://zipzip.ru/search/?q={item}"
    html = await fetch(session, url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for prod in soup.select(".item_info"):
        name = prod.select_one(".item-title")
        price = prod.select_one(".price_value")
        if name and price:
            try:
                price_val = float(price.text.strip().split()[0].replace(",", "."))
            except Exception:
                continue
            products.append((name.text.strip(), price_val, url))
    return pick_best_product(products, item, "zipzip.ru", url)
# --------------------------------------


async def find_price_for_item(session, item: str):
    for search_func in [search_chipdip_api, search_laserparts, search_tze1, search_zipzip]:
        try:
            result = await search_func(session, item)
            if result:
                price, site, url, found_name = result
                score = match_score(item, found_name)
                return price, site, url, found_name, score
        except Exception as e:
            logging.warning(f"Ошибка при поиске {item}: {e}")
    return None, None, None, None, 0


def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


async def process_items(input_file: str, output_file: str):
    with open(input_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        items = [row[0].strip() for row in reader if row]

    processed = set()
    results = []

    if os.path.exists(output_file):
        with open(output_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    item = row.get("item", "").strip()
                    if item:
                        processed.add(item)
                        results.append((
                            item,
                            row.get("price_rub", ""),
                            row.get("source_site", ""),
                            row.get("source_url", ""),
                            row.get("match_score", "0")
                        ))
                except Exception as e:
                    logging.warning(f"Ошибка чтения строки {row}: {e}")
        print(f"🔄 Продолжаем с места остановки. Уже обработано: {len(processed)} строк")

    remaining_items = [it for it in items if it not in processed]

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        with tqdm(total=len(remaining_items), desc="Обработка", unit="шт") as pbar:
            for idx, batch in enumerate(chunked(remaining_items, BATCH_SIZE), 1):
                tasks = [find_price_for_item(session, item) for item in batch]
                batch_results = await asyncio.gather(*tasks)

                for item, (price, site, url, name, score) in zip(batch, batch_results):
                    if not price or score < 70:
                        logging.warning(f"Не найдено: {item} (score={score})")
                    else:
                        results.append((item, f"{price:.2f}", site, url, score))
                    pbar.update(1)

                if len(results) % SAVE_EVERY == 0:
                    with open(output_file, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["item", "price_rub", "source_site", "source_url", "match_score"])
                        writer.writerows(results)
                    print(f"--- Сохранено промежуточно: {len(results)} строк")

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["item", "price_rub", "source_site", "source_url", "match_score"])
        writer.writerows(results)

    print(f"✅ Готово. Всего записано: {len(results)} строк → {output_file}")
    print(f"⚠️ Ошибки смотри в {LOG_FILE}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 scraper.py source.csv output.csv")
        sys.exit(1)

    asyncio.run(process_items(sys.argv[1], sys.argv[2]))
