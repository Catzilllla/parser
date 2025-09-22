import os

# Список сайтов
sites = [
    "https://www.xcom-shop.ru/",
    "https://business.market.yandex.ru/",
    "https://www.ozon.ru/",
    "https://bulat-group.ru/",
    "https://www.regard.ru/",
    "https://www.partsdirect.ru/",
    "https://www.onlinetrade.ru/",
    "https://www.citilink.ru/",
    "https://zip.re/",
    "http://shesternya-zip.ru/",
    "https://www.dns-shop.ru/",
    "https://www.kyoshop.ru/",
    "https://pantum-shop.ru/",
    "https://www.kns.ru/",
    "https://pantum-store.ru/",
    "https://ink-market.ru/",
    "https://www.printcorner.ru/",
    "https://cartridge.ru/",
    "https://4printers.ru/",
    "https://opticart.ru/",
    "https://www.lazerka.net/",
    "https://imprints.ru/",
    "https://kartridgmsk.ru/"
]

# Функция для создания "чистого" имени из URL
def get_name_from_url(url):
    name = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    name = name.replace(".", "_").replace("-", "_")
    return name

# Основной цикл
for site in sites:
    folder_name = get_name_from_url(site)
    os.makedirs(folder_name, exist_ok=True)
    
    # Создаем файл с ссылкой
    with open(os.path.join(folder_name, "link.txt"), "w", encoding="utf-8") as f:
        f.write(site)
    
    # Создаем пустой lowRequest.py
    open(os.path.join(folder_name, "lowRequest.py"), "w", encoding="utf-8").close()
    
    # Создаем base{name}.py
    base_file = f"base{folder_name}.py"
    open(os.path.join(folder_name, base_file), "w", encoding="utf-8").close()

print("Папки и файлы успешно созданы!")
