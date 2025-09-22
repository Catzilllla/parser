#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Обновлённый боевой однопоточный парсер (исправлена логика перехода по первой ссылке Google).
- читает source100.csv (один столбец)
- для каждой строки: парсит a,b,c
- делает безопасный запрос в Google, логирует URL и первую ссылку SERP
- извлекает реальную целевую ссылку (удаляет /url?q=...)
- переходит по этой ссылке и пытается найти цену товара (по артикулам -> по a/b)
- сохраняет результат в result.csv и логирует в parser.log

pip install requests beautifulsoup4 rapidfuzz
"""

import csv
import re
import time
import random
import logging
from typing import List, Tuple, Optional, Dict
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

# ----------------------------
# Настройки
# ----------------------------
INPUT_FILE = "source100.csv"
OUTPUT_FILE = "result.csv"
LOG_FILE = "parser.log"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
]

REQUEST_TIMEOUT = 12  # секунд
PAUSE_MIN = 3.0
PAUSE_MAX = 7.0

PRICE_REGEX = re.compile(r"(\d{1,3}(?:[ \u00A0]\d{3})*(?:[.,]\d{2})?)\s?(?:₽|руб|RUB|rub)", re.IGNORECASE)
ARTICLES_END_RE = re.compile(r"((?:[A-Za-z0-9\-]+)(?:/[A-Za-z0-9\-]+)*)\s*$")

# ----------------------------
# Логирование
# ----------------------------
def setup_logger():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8"
    )

def log(msg: str, level: str = "info"):
    if level.lower() == "error":
        logging.error(msg)
    elif level.lower() == "warning":
        logging.warning(msg)
    else:
        logging.info(msg)
    print(msg)

# ----------------------------
# CSV I/O
# ----------------------------
def read_input(filepath: str) -> List[str]:
    items = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            val = row[0].strip()
            # allow empty lines but skip pure-empty
            items.append(val)
    log(f"Прочитано {len(items)} строк из {filepath}")
    return items

def save_results(results: List[Dict], filepath: str):
    fieldnames = [
        "input_line", "a", "b", "articles", "google_query_url", "first_link", "price_raw", "price_numeric_rub", "matched_by"
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    log(f"Сохранено {len(results)} строк в {filepath}")

# ----------------------------
# Парсер a,b,c
# ----------------------------
def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.lower()
    s = s.replace(".", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def parse_expression(text: str) -> Tuple[str, str, List[str]]:
    text = text.strip()
    articles: List[str] = []
    m = ARTICLES_END_RE.search(text)
    if m:
        maybe = m.group(1)
        if re.search(r"[A-Za-z0-9\-]", maybe):
            articles = [x.strip() for x in maybe.split("/") if x.strip()]
            text = text[:m.start()].strip()
    parts = text.split(maxsplit=1)
    a = parts[0].strip() if parts else ""
    b = parts[1].strip() if len(parts) > 1 else ""
    return normalize_text(a), normalize_text(b), articles

# ----------------------------
# Формируем безопасный Google-запрос и извлекаем первую ссылку
# ----------------------------
def build_query(a: str, b: str, articles: List[str]) -> str:
    q_parts = []
    if a:
        q_parts.append(a)
    if b:
        q_parts.append(b)
    if articles:
        q_parts.append(articles[0])
    return " ".join(q_parts).strip()

def _extract_target_from_href(href: str) -> Optional[str]:
    """Извлекает целевой URL из href вида '/url?q=TARGET&sa=...'
    или возвращает href если это уже полный http(s) URL.
    """
    if not href:
        return None
    # Google redirect pattern
    if href.startswith("/url?q="):
        # take part after /url?q= up to & 
        try:
            after = href.split("/url?q=", 1)[1]
            target = after.split("&", 1)[0]
            return target
        except Exception:
            return None
    # If it's direct http(s) link
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return None

def safe_google_search(query: str) -> Tuple[Optional[str], Optional[str]]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    }
    encoded = quote_plus(query)
    search_url = f"https://www.google.com/search?q={encoded}"
    log(f"[GOOGLE] Запрос: {search_url}")

    try:
        resp = requests.get(search_url, headers=headers, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        log(f"[GOOGLE] Ошибка запроса: {e}", level="error")
        return search_url, None

    if resp.status_code != 200:
        log(f"[GOOGLE] HTTP {resp.status_code} при запросе: {search_url}", level="warning")
        return search_url, None

    soup = BeautifulSoup(resp.text, "html.parser")
    first_link = None

    # Strategy 1: new SERP structure - div.yuRUbf > a (often contains the target)
    try:
        a_tag = soup.select_one("div.yuRUbf > a[href]")
        if a_tag and a_tag.get("href"):
            href = a_tag.get("href")
            target = _extract_target_from_href(href) or href
            first_link = target
    except Exception:
        first_link = None

    # Strategy 2: links in result containers with /url?q=
    if not first_link:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            target = _extract_target_from_href(href)
            if target:
                # skip google-internal caches and google domains
                parsed = urlparse(target)
                hostname = parsed.hostname or ""
                if "google" in hostname.lower() or "webcache" in hostname.lower():
                    continue
                first_link = target
                break

    # Strategy 3: fallback to first http(s) link that is not google
    if not first_link:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                parsed = urlparse(href)
                hostname = parsed.hostname or ""
                if "google" in hostname.lower() or "translate.google" in hostname.lower():
                    continue
                first_link = href
                break

    if first_link:
        log(f"[GOOGLE] Первая ссылка (целевой URL): {first_link}")
    else:
        log("[GOOGLE] Не удалось найти первую ссылку в выдаче", level="warning")

    return search_url, first_link

# ----------------------------
# Загрузка страницы и поиск цены
# ----------------------------
def fetch_page(url: str) -> Optional[requests.Response]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
        "Referer": "https://www.google.com/"
    }
    try:
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return r
        else:
            log(f"[FETCH] HTTP {r.status_code} при заходе на {url}", level="warning")
    except Exception as e:
        log(f"[FETCH] Ошибка при заходе на {url}: {e}", level="error")
    return None

def find_price_in_text_block(text_block: str) -> Optional[str]:
    if not text_block:
        return None
    m = PRICE_REGEX.search(text_block)
    if m:
        return m.group(0)
    return None

def extract_price_from_soup_for_articles(soup: BeautifulSoup, articles: List[str]) -> Tuple[Optional[str], Optional[str]]:
    page_text = soup.get_text(separator=" ", strip=True)
    for art in articles:
        if not art:
            continue
        idx = page_text.lower().find(art.lower())
        if idx != -1:
            start = max(0, idx - 500)
            end = min(len(page_text), idx + 500)
            window = page_text[start:end]
            price = find_price_in_text_block(window)
            if price:
                return price, "article_text"
    for art in articles:
        if not art:
            continue
        candidates = soup.find_all(string=re.compile(re.escape(art), re.IGNORECASE))
        for cand in candidates:
            parent = cand.parent
            for _ in range(4):
                if not parent:
                    break
                text_block = parent.get_text(" ", strip=True)
                price = find_price_in_text_block(text_block)
                if price:
                    return price, "article_dom"
                parent = parent.parent
    return None, None

def extract_price_from_soup_for_name(soup: BeautifulSoup, a: str, b: str) -> Tuple[Optional[str], Optional[str]]:
    page_text = soup.get_text(separator=" ", strip=True)
    name_target = " ".join(filter(None, [a, b])).strip()
    if not name_target:
        price = find_price_in_text_block(page_text)
        if price:
            return price, "any_price_fallback"
        return None, None
    blocks = re.split(r"[>\n\r\t]+", page_text)
    best_score = 0
    best_block = None
    for block in blocks:
        if not block.strip():
            continue
        score = fuzz.ratio(normalize_text(name_target), normalize_text(block))
        if score > best_score:
            best_score = score
            best_block = block
    if best_block and best_score >= 65:
        price = find_price_in_text_block(best_block)
        if price:
            return price, f"name_fuzzy_{int(best_score)}"
    price = find_price_in_text_block(page_text)
    if price:
        return price, "any_price_fallback"
    return None, None

def parse_price_to_number(price_raw: str) -> Optional[int]:
    if not price_raw:
        return None
    m = re.search(r"([\d \u00A0]+)(?:[.,]\d{2})?", price_raw)
    if not m:
        return None
    digits = m.group(1).replace("\u00A0", "").replace(" ", "")
    try:
        return int(digits)
    except Exception:
        try:
            return int(float(digits))
        except Exception:
            return None

# ----------------------------
# Обработка одной строки (гарантированный переход по первой ссылке)
# ----------------------------
def process_line(input_line: str) -> Dict:
    a, b, articles = parse_expression(input_line)
    query = build_query(a, b, articles)
    search_url, first_link = safe_google_search(query)

    result = {
        "input_line": input_line,
        "a": a,
        "b": b,
        "articles": ";".join(articles) if articles else "",
        "google_query_url": search_url or "",
        "first_link": first_link or "",
        "price_raw": "",
        "price_numeric_rub": "",
        "matched_by": ""
    }

    if not first_link:
        log(f"[PROCESS] Нет первой ссылки для '{input_line}'", level="warning")
        return result

    # Если first_link всё ещё содержит google-редирект /url?q=..., извлечём целевой URL
    parsed_first = first_link
    if parsed_first.startswith("/url?q="):
        parsed_first = parsed_first.split("/url?q=", 1)[1].split("&", 1)[0]

    # Если ссылка относительная (скорее маловероятно) — сделать полную через Google origin
    if parsed_first.startswith("/"):
        parsed_first = urljoin("https://www.google.com", parsed_first)

    log(f"[PROCESS] Переходим по первой ссылке: {parsed_first}")
    r = fetch_page(parsed_first)
    if r is None:
        log(f"[PROCESS] Не удалось загрузить первую ссылку: {parsed_first}", level="warning")
        return result

    soup = BeautifulSoup(r.text, "html.parser")

    # 1) Попробуем найти цену по артикулам
    price_raw, matched = extract_price_from_soup_for_articles(soup, articles)
    if price_raw:
        num = parse_price_to_number(price_raw)
        result.update({"price_raw": price_raw, "price_numeric_rub": num if num is not None else "", "matched_by": matched})
        log(f"[FOUND] По article на {parsed_first}: {price_raw} (num={num})")
        return result

    # 2) Попробуем найти цену по a+b
    price_raw, matched = extract_price_from_soup_for_name(soup, a, b)
    if price_raw:
        num = parse_price_to_number(price_raw)
        result.update({"price_raw": price_raw, "price_numeric_rub": num if num is not None else "", "matched_by": matched})
        log(f"[FOUND] По name на {parsed_first}: {price_raw} (num={num}), match={matched}")
        return result

    log(f"[NOTFOUND] Цена не найдена на странице {parsed_first}", level="warning")
    return result

# ----------------------------
# Основной цикл
# ----------------------------
def main():
    setup_logger()
    items = read_input(INPUT_FILE)
    results = []

    for idx, line in enumerate(items, start=1):
        log(f"--- Обработка {idx}/{len(items)}: '{line}' ---")
        try:
            res = process_line(line)
            results.append(res)
        except Exception as e:
            log(f"[CRITICAL] Ошибка при обработке строки '{line}': {e}", level="error")
            results.append({
                "input_line": line,
                "a": "", "b": "", "articles": "", "google_query_url": "", "first_link": "",
                "price_raw": "", "price_numeric_rub": "", "matched_by": "error"
            })
        sleep_t = random.uniform(PAUSE_MIN, PAUSE_MAX)
        log(f"Пауза {sleep_t:.2f} с.")
        time.sleep(sleep_t)

    save_results(results, OUTPUT_FILE)
    log("Готово.")

if __name__ == "__main__":
    main()
