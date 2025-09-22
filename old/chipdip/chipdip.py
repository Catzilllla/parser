import aiohttp
import asyncio
import pandas as pd
import logging
from tqdm import tqdm
import random
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("parser.log"),
        logging.StreamHandler()
    ]
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": "https://www.chipdip.ru/",
    "X-Requested-With": "XMLHttpRequest",
}

BASE_URL = "https://www.chipdip.ru/searchajax?searchtext={}"

CONCURRENT_REQUESTS = 5
DELAY_BETWEEN_REQUESTS = (0.2, 0.6)
MAX_RETRIES = 3


async def fetch_price(session, semaphore, item_name):
    """Парсинг цены для одного товара с повторами"""
    url = BASE_URL.format(item_name)
    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url, headers=HEADERS) as resp:
                    if resp.status != 200:
                        logging.warning(f"Ошибка {resp.status} для {item_name} (попытка {attempt})")
                        await asyncio.sleep(1)
                        continue

                    data = await resp.json()
                    prices = []
                    for product in data.get("products", []):
                        for offer in product.get("offers", []):
                            if "price" in offer:
                                try:
                                    prices.append(float(offer["price"]))
                                except Exception:
                                    pass

                    await asyncio.sleep(random.uniform(*DELAY_BETWEEN_REQUESTS))
                    return max(prices) if prices else None

            except Exception as e:
                logging.error(f"Ошибка при {item_name} (попытка {attempt}): {e}")
                await asyncio.sleep(1)

        return None


async def process_excel(input_file, output_file):
    df = pd.read_excel(input_file)

    if df.shape[1] > 1:
        df = df.iloc[:, [0]]

    df.columns = ["Наименование"]
    df["Цена"] = None

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_price(session, semaphore, str(row["Наименование"]))
            for _, row in df.iterrows()
        ]

        results = []
        with tqdm(total=len(tasks), desc="Парсинг", unit="товар", ncols=100) as pbar:
            for f in asyncio.as_completed(tasks):
                res = await f
                results.append(res)
                pbar.update(1)

    df["Цена"] = results
    df.to_excel(output_file, index=False)
    logging.info(f"Готово! Результат сохранён в {output_file}")


if __name__ == "__main__":
    input_file = os.path.join("input", "priceSetTable.xlsx")
    output_file = os.path.join("output", "output.xlsx")

    if not os.path.exists(input_file):
        logging.error("Файл priceSetTable.xlsx не найден в папке input/")
    else:
        asyncio.run(process_excel(input_file, output_file))
