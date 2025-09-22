import pandas as pd

# --- Файлы ---
input_csv = "source/source.csv"          # исходный файл
output_csv = "parts_unique.csv"  # файл с уникальными значениями

# --- Чтение CSV ---
df = pd.read_csv(input_csv, header=None, names=["part_name"])

# --- Удаляем дубликаты без учета регистра ---
df["part_name_lower"] = df["part_name"].str.lower()  # приводим к нижнему регистру
df_unique = df.drop_duplicates(subset=["part_name_lower"], keep="first").drop(columns=["part_name_lower"])

# --- Сохраняем в новый CSV ---
df_unique.to_csv(output_csv, index=False)

print(f"Дубликаты удалены (без учета регистра), уникальные значения сохранены в {output_csv}")
