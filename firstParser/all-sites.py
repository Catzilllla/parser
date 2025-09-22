import requests
import csv
import time
import random
import logging
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("parser.log", encoding="utf-8"), logging.StreamHandler()]
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

SITES = [
    {"url": "https://www.xcom-shop.ru/", "method": "api"},
    {"url": "https://business.market.yandex.ru/", "method": "api"},
    {"url": "https://www.bulat-group.ru/", "method": "html"},
    {"url": "https://www.regard.ru/", "method": "api"},
    {"url": "https://www.citilink.ru/", "method": "api"},
    {"url": "https://zip.re/", "method": "api"},
    {"url": "http://shesternya-zip.ru/", "method": "html"},
    {"url": "https://pantum-shop.ru/", "method": "api"},
    {"url": "https://www.kns.ru/", "method": "html"},
    {"url": "https://ink-market.ru/", "method": "api"},
    {"url": "https://www.printcorner.ru/", "method": "api"},
    {"url": "https://cartridge.ru/", "method": "api"},
    {"url": "https://opticart.ru/", "method": "api"},
    {"url": "https://www.lazerka.net/", "method": "api"},
    {"url": "https://imprints.ru/", "method": "html"},
    {"url": "https://kartridgmsk.ru/", "method": "api"},
]

def log_step(step, msg):
    logging.info(f"[{step}] {msg}")

def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        logging.warning(f"Ошибка запроса {url}: {e}")
        return None

def parse_html_price_xcom(name, article):
    """Пример парсера XCOM (HTML поиска → цена)."""
    search_url = f"https://www.xcom-shop.ru/search/?text={article}"
    log_step("XCOM", f"Запрос: {search_url}")
    html = safe_request(search_url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    price_tag = soup.select_one(".b-product-list__price")
    if price_tag:
        price = price_tag.get_text(strip=True).replace("₽", "").replace(" ", "")
        return price
    return None

def process_item(name, article):
    """Обработка одного товара."""
    log_step("PROCESS", f"Ищем {article} | {name}")
    for site in SITES:
        if "xcom-shop.ru" in site["url"]:
            price = parse_html_price_xcom(name, article)
            if price:
                log_step("FOUND", f"{article} | {price} руб. [{site['url']}]")
                return price, site["url"]
        # TODO: добавить обработчики для остальных сайтов
    return None, None

def main():
    results = []
    with open("source100.csv", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # пропускаем заголовок
        for i, row in enumerate(reader, 1):
            if not row:
                continue
            article = row[0].strip()
            name = row[0].strip()  # можно разделить, если в CSV разные столбцы
            log_step("ITEM", f"{i}: {name}")
            price, site = process_item(name, article)
            results.append([article, name, price if price else "", site if site else ""])
            time.sleep(random.uniform(3, 7))  # антибан

    with open("result.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["article", "name", "price_rub", "source"])
        writer.writerows(results)

    log_step("DONE", f"Обработка завершена. Найдено {len(results)} позиций.")

if __name__ == "__main__":
    main()
