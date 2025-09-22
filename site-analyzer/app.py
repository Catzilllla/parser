from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from analyzer import check_site

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# список сайтов по умолчанию
default_sites = [
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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "sites": [], "default_sites": default_sites})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request, sites: str = Form(...)):
    sites_list = [s.strip() for s in sites.splitlines() if s.strip()]
    results = [check_site(site) for site in sites_list]
    return templates.TemplateResponse("index.html", {"request": request, "sites": results, "default_sites": sites_list})
