import requests
import openpyxl
import time
from typing import Dict, Any


def run_scraper(job_id: str, file_path: str, tasks: Dict[str, Any]):
    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active

        rows = list(ws.iter_rows(min_row=2, values_only=True))  # пропускаем заголовок
        total = len(rows)
        results = []

        for i, (name, target_price) in enumerate(rows, start=1):
            query = str(name).strip()
            found_prices = []

            # Парсим каждую часть артикула
            for part in query.replace("/", " ").split():
                if "-" in part or part.isalnum():
                    try:
                        r = requests.get(
                            "https://www.chipdip.ru/search",
                            params={"searchtext": part, "json": "1"},
                            timeout=10,
                        )
                        if r.status_code == 200:
                            data = r.json()
                            for item in data.get("Result", []):
                                if item.get("Articul") == part:
                                    price_str = item.get("Price", "0").replace(" ", "")
                                    try:
                                        found_prices.append(float(price_str))
                                    except ValueError:
                                        pass
                    except Exception as e:
                        print(f"Ошибка при запросе {part}: {e}")

            if found_prices:
                results.append({
                    "name": query,
                    "target_price": target_price,
                    "found_price": min(found_prices),  # берём минимальную цену
                    "match": True
                })
            else:
                results.append({
                    "name": query,
                    "target_price": target_price,
                    "found_price": None,
                    "match": False
                })

            tasks[job_id]["progress"] = int(i / total * 100)
            time.sleep(1)  # чтобы не спамить API

        tasks[job_id]["progress"] = 100
        tasks[job_id]["status"] = "done"
        tasks[job_id]["result"] = results

    except Exception as e:
        tasks[job_id]["status"] = "error"
        tasks[job_id]["error"] = str(e)
