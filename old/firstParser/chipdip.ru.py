#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Боевой парсер для chipdip.ru (search -> product pages -> parse)
Функции:
 - rate-limited запросы с retry/backoff
 - рандомные User-Agent и ротация прокси из файла (если есть)
 - парсинг "a, b, c" по правилам (a: кол-во/характеристика, b: описание, c: список артикулов через '/')
 - сохранение результата в CSV

Запуск:
    python chipdip_scraper.py

Настройки:
 - PROXIES_FILE: файл с прокси в формате host:port или user:pass@host:port (по одному в строке)
 - QUERIES: список поисковых строк (пример в коде)
"""

import time
import random
import csv
import re
import logging
from typing import List, Optional, Tuple
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

# ---------- Настройки ----------
OUTPUT_CSV = "chipdip_results.csv"
PROXIES_FILE = "proxies.txt"   # optional: one proxy per line host:port or user:pass@host:port
MAX_WORKERS = 3                # кол-во одновременных потоков (если используешь async, но здесь синхронно)
MIN_DELAY = 1.2                # минимальная пауза между запросами в секундах
MAX_DELAY = 3.5                # максимальная пауза (рандом)
MAX_RETRIES = 4
BACKOFF_FACTOR = 1.2
TIMEOUT = 15                   # секунд
LOG_LEVEL = logging.INFO
# -------------------------------

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Набор User-Agent — расширь по мере нужды
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
]

# Простейшая ротация прокси
def load_proxies(filename: str) -> List[str]:
    p = Path(filename)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        ln = line.strip()
        if not ln or ln.startswith("#"):
            continue
        out.append(ln)
    return out

PROXIES = load_proxies(PROXIES_FILE)


def build_session(proxy: Optional[str] = None) -> requests.Session:
    s = requests.Session()
    # Retry на уровне адаптера
    retries = Retry(total=MAX_RETRIES, backoff_factor=BACKOFF_FACTOR,
                    status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["HEAD", "GET", "OPTIONS"])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))

    # Базовые заголовки; User-Agent будем менять перед каждым запросом
    s.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Referer": "https://www.chipdip.ru/",
        "Upgrade-Insecure-Requests": "1",
    })
    # прокси (requests формат)
    if proxy:
        s.proxies.update({
            "http": proxy,
            "https": proxy,
        })
    return s


def random_pause():
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    # jitter
    jitter = random.uniform(0.0, 0.6)
    total = delay + jitter
    logger.debug(f"sleep {total:.2f}s")
    time.sleep(total)


def safe_get(session: requests.Session, url: str, params: dict = None, allow_redirects: bool = True) -> Optional[requests.Response]:
    # обновляй User-Agent каждый раз
    ua = random.choice(USER_AGENTS)
    session.headers["User-Agent"] = ua

    # иногда стоит обновлять Referer случайным образом
    # session.headers["Referer"] = "https://www.chipdip.ru/"

    try:
        resp = session.get(url, params=params, timeout=TIMEOUT, allow_redirects=allow_redirects)
        # Если сайт возвращает 403/401/429 — нужно обработать отдельно
        if resp.status_code == 403:
            logger.warning(f"403 Forbidden for {url}")
            return None
        if resp.status_code == 401:
            logger.warning(f"401 Unauthorized for {url}")
            return None
        if resp.status_code == 429:
            logger.warning(f"429 Too Many Requests for {url}")
            return None
        # всё ок
        return resp
    except requests.RequestException as e:
        logger.warning(f"Request failed: {e} for {url}")
        return None


# ---------- Парсинг названия + артикула (a,b,c) ----------
# Возвращаем a, b, list[c]
ARTICLE_PATTERN = re.compile(r"((?:[A-Za-zА-Яа-я0-9]+-[A-Za-zА-Яа-я0-9-]+[A-Za-zA-Яа-я0-9]*)|[A-Z0-9-]{4,})")
# Паттерн списка артикулов в конце вида AAA-BBB-CCC/DDD-EEE
ARTS_AT_END_RE = re.compile(r"((?:[A-Za-z0-9\-]+)(?:/(?:[A-Za-z0-9\-]+))+)$")
# Для выделения a: число + слово(либо слово-часть), допустим "100-лист", "1шт", "2 шт."
A_PART_RE = re.compile(r"^\s*([\d\w\-]+(?:[ \u00A0]?(?:шт|лист|pack|pcs|комп|шт\.)?)?)\.?\s*", re.IGNORECASE)

def parse_a_b_c(text: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    if not text:
        return None, None, []
    t = text.strip()
    # 1) Ищем список артикулов в конце
    articles = []
    m = ARTS_AT_END_RE.search(t)
    if m:
        arts_raw = m.group(1)
        articles = [a.strip() for a in arts_raw.split("/") if a.strip()]
        t = t[:m.start()].strip()

    # 2) Ищем a (число/характеристика) в начале
    a = None
    b = None
    ma = A_PART_RE.match(t)
    if ma:
        a = ma.group(1).strip().rstrip(".")
        b = t[ma.end():].strip()
    else:
        # нет явного a — можно попытаться разбить на первые 1-2 слова
        parts = t.split(None, 1)
        a = parts[0] if parts else None
        b = parts[1] if len(parts) > 1 else None

    # Нормализация: убрать лишние точки и пробелы
    if a:
        a = re.sub(r"\s+", " ", a).strip().strip(".")
    if b:
        b = re.sub(r"\s+", " ", b).strip().strip(".")
    return a, b, articles

# ---------- Поиск ссылок на странице поиска ----------
# Стараться отлавливать ссылки на карточки товара.
POSSIBLE_PRODUCT_URL_RE = re.compile(r"^(?:/catalog/|/product/|/item/|/cards/|/product-card/|/product/\d+)", re.IGNORECASE)

def find_product_links(html: str, base_url: str = "https://www.chipdip.ru") -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # нормализуем относительные ссылки
        if href.startswith("/"):
            full = base_url.rstrip("/") + href
        elif href.startswith("http"):
            full = href
        else:
            continue

        # простая эвристика: содержит шаблон product или /catalog/ или длинный path с артикулом
        if ("/catalog/" in href) or ("/product" in href) or (re.search(r"/card/|/item/|/product-card", href)):
            links.add(full)
        else:
            # fallback: если текст ссылки содержит слово "Купить" или "Подробнее"
            txt = (a.get_text() or "").lower()
            if "купить" in txt or "подробнее" in txt or "в корзину" in txt:
                links.add(full)
    return list(links)


# ---------- Основная логика: поиск -> посещение карточек -> парсинг ----------
def process_search(query: str, session: requests.Session, proxy: Optional[str] = None) -> List[dict]:
    results = []
    search_url = "https://www.chipdip.ru/search"
    params = {"searchtext": query}

    logger.info(f"Searching for: {query} (proxy={proxy})")
    resp = safe_get(session, search_url, params=params)
    if not resp or resp.status_code != 200:
        logger.warning(f"No search results for '{query}' (status: {getattr(resp, 'status_code', None)})")
        return results

    product_links = find_product_links(resp.text)
    logger.info(f"Found {len(product_links)} product links (heuristic) for query '{query}'")
    # ограничь глубину, если нужно
    # product_links = product_links[:10]

    for link in product_links:
        # пауза перед запросом карточки
        random_pause()
        r = safe_get(session, link)
        if not r or r.status_code != 200:
            logger.warning(f"Skip link {link}")
            continue
        # парсим название карточки
        soup = BeautifulSoup(r.text, "html.parser")
        # эвристика выбор названия: заголовки h1/h2, meta og:title, title
        title = None
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("h2"):
            title = soup.find("h2").get_text(strip=True)
        if not title:
            meta_og = soup.find("meta", property="og:title")
            if meta_og and meta_og.get("content"):
                title = meta_og["content"]
        if not title:
            title = soup.title.string if soup.title else ""

        a, b, articles = parse_a_b_c(title)

        # дополнительные попытки найти артикулы в тексте страницы (таблицы характеристик)
        if not articles:
            # ищем patterns в тексте: типичные артикула (буквы-цифры с дефисами)
            page_text = soup.get_text(" ", strip=True)
            # ищем все подходящие по длине/формату
            found = re.findall(r"\b[A-Z0-9]{2,4}[-][A-Z0-9\-]{2,}\b", page_text, flags=re.IGNORECASE)
            # фильтруем/уникализируем
            found = [f for f in dict.fromkeys(found)]  # preserve order, unique
            if found:
                # можно выбрать первые N
                articles = found[:6]

        results.append({
            "query": query,
            "product_url": link,
            "title": title,
            "a": a,
            "b": b,
            "articles": "|".join(articles) if articles else "",
        })
    return results

def main():
    # пример запросов — замени на свои
    QUERIES = [
        "Шлейф панели Sharp QCNW-0208FCZZ",
        "RM1-1740-040CN",
    ]

    # Режим прокси: цикл по прокси, если есть
    proxies_list = PROXIES
    proxy_cycle = proxies_list[:] if proxies_list else [None]

    all_results = []

    for i, q in enumerate(QUERIES):
        proxy = random.choice(proxy_cycle) if proxy_cycle else None
        sess = build_session(proxy=proxy)
        # если у тебя есть cookies, их можно установить здесь:
        # sess.cookies.update({...})

        res = process_search(q, sess, proxy=proxy)
        all_results.extend(res)

        # делаем паузу между запросами к сайту
        random_pause()

    # записываем CSV
    fieldnames = ["query", "product_url", "title", "a", "b", "articles"]
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_results:
            writer.writerow(row)

    logger.info(f"Saved {len(all_results)} records to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
