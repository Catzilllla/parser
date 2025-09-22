import pandas as pd
import requests
from bs4 import BeautifulSoup
from time import sleep
from tqdm import tqdm

# --- Функция запроса и парсинга ---
def fetch_part_results(part, url, headers, cookies):
    data = {
        'setsearchdata': '1',
        'search_type': 'all',
        'category_id': '0',
        'search': part,
        'acategory_id': '0',
    }

    results = []
    try:
        response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Находим все блоки товаров
            items = soup.select("div.product")
            if not items:
                results.append({"part": part, "name": None, "price": None})
            for item in items:
                # Название
                name_tag = item.select_one("div.name a")
                name = name_tag.get_text(strip=True) if name_tag else None
                
                # Цена
                price_tag = item.select_one("div.jshop_price span")
                price = price_tag.get_text(strip=True) if price_tag else None
                
                results.append({"part": part, "name": name, "price": price})
        else:
            results.append({"part": part, "name": None, "price": None})
    except Exception as e:
        results.append({"part": part, "name": None, "price": None})
    
    return results

# --- Основной скрипт ---
def main():
    input_csv = "source100.csv"
    output_csv = "search_results_parsed.csv"
    url = "https://vce-o-printere.ru/search/result.html"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Referer': 'https://vce-o-printere.ru/komplektuyuschie-zip-dlya-printera/zip-hp/raznoe-hp/hp-jc0700020a-lcd-displey-jc0700020a-lcd-displey-zapchasti-panel-upravleniya-jc0700020a-dlya-modeley-lj-mfp-m433.html',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://vce-o-printere.ru',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    cookies = {
        '90a27748f029670aa3b56d4ff1180f2d': 'b24d68177cd0c1a670d56b37fdde4c1c',
        'supportOnlineTalkID': 'mS8PChH1vpl4cKALyuVvhEPqBLRckaZG',
    }

    df = pd.read_csv(input_csv, header=None, names=["part_name"])
    all_results = []

    for part in tqdm(df["part_name"], desc="Обработка деталей"):
        part_results = fetch_part_results(part, url, headers, cookies)
        all_results.extend(part_results)
        sleep(1)  # задержка, чтобы не заблокировали сайт

    output_df = pd.DataFrame(all_results)
    output_df.to_csv(output_csv, index=False)
    print(f"Поиск завершён, результаты сохранены в {output_csv}")

if __name__ == "__main__":
    main()
