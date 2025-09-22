import csv
import aiohttp
import asyncio
import logging
import os
from rapidfuzz import fuzz

# Логирование ошибок
logging.basicConfig(filename="errors.log", level=logging.WARNING, encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "Referer": "https://www.chipdip.ru/",
    "Connection": "keep-alive",
}


async def search_chipdip_api(session, item: str):
    """
    Поиск товара через Chipdip API
    Берём только точное совпадение по артикулу
    """
    url = f"https://www.chipdip.ru/ajaxsearch?searchtext={item}"
    try:
        async with session.get(url, headers=HEADERS) as resp:
            if resp.status != 200:
                logging.warning(f"Chipdip API вернул {resp.status} для {item}")
                return None

            data = await resp.json(content_type=None)
            if not data or "items" not in data:
                return None

            # Ищем точное совпадение по артикулу
            for found in data["items"]:
                found_name = found.get("Name", "").strip()
                if item.lower() in found_name.lower():
                    try:
                        price_val = float(str(found.get("Price", "0")).replace(",", "."))
                    except Exception:
                        price_val = None
                    url = "https://www.chipdip.ru" + found.get("Url", "")
                    if price_val:
                        return price_val, "chipdip.ru", url, found_name
    except Exception as e:
        logging.warning(f"Chipdip API error для {item}: {e}")
    return None


def load_items(input_file: str):
    """
    Загружает артикулы из CSV
    Поддержка файлов с заголовком 'item' и без заголовков
    """
    with open(input_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return []

    # Если первая строка явно содержит заголовок
    if rows[0] and rows[0][0].lower() == "item":
        with open(input_file, newline="", encoding="utf-8") as f:
            dict_reader = csv.DictReader(f)
            return [row["item"] for row in dict_reader if row.get("item")]
    else:
        # Просто берём первую колонку
        return [row[0] for row in rows if row]


async def process_items(input_file, output_file, progress_callback=None):
    """
    Основной процесс обработки:
    - читает source.csv
    - ищет цены
    - пишет output.csv
    """
    results = []
    processed = set()

    # Если output.csv уже существует — продолжаем
    if os.path.exists(output_file):
        with open(output_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append((
                    row.get("item", ""),
                    row.get("price_rub", ""),
                    row.get("source_site", ""),
                    row.get("source_url", ""),
                    row.get("match_score", "0"),
                ))
                processed.add(row.get("item", ""))

    # Загружаем список артикулов
    items = load_items(input_file)
    total = len(items)
    done = 0

    async with aiohttp.ClientSession() as session:
        for item in items:
            if item in processed:
                done += 1
                if progress_callback:
                    progress_callback(done, total)
                continue

            result = await search_chipdip_api(session, item)
            if result:
                price, site, url, found_name = result
                score = fuzz.ratio(item.lower(), found_name.lower())
                if score >= 70:
                    results.append((item, price, site, url, score))
            else:
                logging.warning(f"Не найдено: {item}")

            done += 1
            if progress_callback:
                progress_callback(done, total)

    # Сохраняем результат
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["item", "price_rub", "source_site", "source_url", "match_score"])
        writer.writerows(results)
