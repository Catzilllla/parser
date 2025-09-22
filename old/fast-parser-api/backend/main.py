import os
import uuid
import threading
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from scraper import run_scraper

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks = {}

@app.get("/")
def root():
    return {"status": "ok", "message": "PriceSet Parser running"}

@app.post("/upload/")
async def upload(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    file_path = f"/tmp/{job_id}.xlsx"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    tasks[job_id] = {"status": "processing", "progress": 0, "result": None}

    threading.Thread(
        target=run_scraper, args=(job_id, file_path, tasks)
    ).start()

    return {"task_id": job_id}

@app.get("/progress/{task_id}")
def progress(task_id: str):
    return tasks.get(task_id, {"status": "not_found"})
