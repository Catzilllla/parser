import requests
from bs4 import BeautifulSoup

def check_site(url):
    result = {"site": url, "rss": False, "api_hint": False, "html": False, "error": None}
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result
        
        text = resp.text.lower()
        
        # RSS
        if "rss" in text or "application/rss+xml" in text:
            result["rss"] = True
        
        # API
        if ".json" in text or "api" in text or "graphql" in text:
            result["api_hint"] = True
        
        # HTML "price"
        soup = BeautifulSoup(resp.text, "lxml")
        if soup.find_all(["div", "span"], class_=lambda c: c and "price" in c.lower()):
            result["html"] = True

    except Exception as e:
        result["error"] = str(e)

    return result
