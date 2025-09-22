import requests
import sqlite3
import pandas as pd
import logging
import time
import random
from bs4 import BeautifulSoup

# --- ЛОГИ ---
logging.basicConfig(
    filename="errors.log",
    filemode="a",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- БД ---
DB_PATH = "chipdip.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    product_name TEXT,
    price TEXT,
    url TEXT,
    status TEXT
)
""")
conn.commit()

# --- ЧТЕНИЕ CSV ---
def load_csv_to_db(csv_file):
    df = pd.read_csv(csv_file)
    for name in df.iloc[:, 0]:
        try:
            cur.execute("INSERT OR IGNORE INTO queries (name) VALUES (?)", (name,))
        except Exception as e:
            logging.error(f"Ошибка при вставке {name}: {e}")
    conn.commit()

# --- ПАРСИНГ CHIPDIP ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0"
}

def chipdip_search(query):
    try:
        url = "https://www.chipdip.ru/search"
        r = requests.get(url, params={"searchtext": query}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        item = soup.select_one(".with-hover a")
        price_block = soup.select_one(".price .price_value")

        if not item:
            return None, None, None, "not_found"
        
        name = item.get("title") or item.text.strip()
        href = "https://www.chipdip.ru" + item.get("href")
        price_text = price_block.get_text(strip=True) if price_block else "нет в наличии"

        return name, price_text, href, "ok"

    except Exception as e:
        logging.error(f"Ошибка при запросе {query}: {e}")
        return None, None, None, "error"


# --- ОСНОВНОЙ ЦИКЛ ---
def run_parser():
    cur.execute("SELECT name FROM queries")
    all_queries = [row[0] for row in cur.fetchall()]

    for query in all_queries:
        name, price, href, status = chipdip_search(query)
        cur.execute(
            "INSERT INTO results (query, product_name, price, url, status) VALUES (?, ?, ?, ?, ?)",
            (query, name, price, href, status)
        )
        conn.commit()
        time.sleep(random.uniform(1, 3))  # антибан

# --- ВЫГРУЗКА CSV ---
def export_results():
    df = pd.read_sql_query("SELECT * FROM results", conn)
    df.to_csv("result.csv", index=False, encoding="utf-8-sig")

# --- Запуск ---
if __name__ == "__main__":
    load_csv_to_db("source100.csv")  # твой файл
    run_parser()
    export_results()
    conn.close()
    print("Готово! Результаты в result.csv, ошибки в errors.log")
