# backend/database.py
import sqlite3
import os

DB = "/data/progress.db"
os.makedirs("/data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        progress INTEGER
    )
    """)
    conn.commit()
    conn.close()

def set_progress(task_id: str, value: int):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO tasks (task_id, progress) VALUES (?, ?)",
              (task_id, int(value)))
    conn.commit()
    conn.close()

def get_progress(task_id: str) -> int:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT progress FROM tasks WHERE task_id=?", (task_id,))
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 0
