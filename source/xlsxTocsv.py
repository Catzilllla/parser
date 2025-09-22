import pandas as pd

def xlsx_onecol_to_csv(input_file: str, output_file: str):
    # Читаем первый лист Excel
    df = pd.read_excel(input_file, engine="openpyxl")

    # Берём только первый столбец
    df = df.iloc[:, [0]]

    # Сохраняем в CSV без индексов
    df.to_csv(output_file, index=False, header=True, encoding="utf-8-sig")
    print(f"Файл {output_file} успешно создан.")

if __name__ == "__main__":
    xlsx_onecol_to_csv("priceSetTable.xlsx", "output.csv")
