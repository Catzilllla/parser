import streamlit as st
import asyncio
import pandas as pd
import os
from scraper import process_items

st.set_page_config(page_title="Price Scraper", layout="wide")
st.title("🔍 Price Scraper — мониторинг цен")

uploaded_file = st.file_uploader("Загрузите CSV файл с артикулами (колонка `item`)", type="csv")
output_file = "output.csv"

if uploaded_file:
    with open("input.csv", "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success("Файл успешно загружен!")

    if st.button("▶️ Запустить поиск"):
        st.info("Скрипт выполняется... Подождите ⏳")

        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(done, total):
            percent = int(done / total * 100)
            progress_bar.progress(percent)
            status_text.text(f"{done}/{total} ({percent}%)")

        asyncio.run(process_items("input.csv", output_file, progress_callback=update_progress))
        st.success("✅ Поиск завершен!")

if os.path.exists(output_file):
    st.subheader("📊 Результаты")
    df = pd.read_csv(output_file)
    st.dataframe(df)
    st.download_button("📥 Скачать CSV", df.to_csv(index=False), "results.csv")

if os.path.exists("errors.log"):
    st.subheader("⚠️ Лог ошибок")
    with open("errors.log", "r", encoding="utf-8") as f:
        st.text(f.read())
