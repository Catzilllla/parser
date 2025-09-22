import requests

cookies = {
    'ANC': '{%22CartSumma%22:%220%22%2C%22CartQty%22:%220%20%D1%82%D0%BE%D0%B2%D0%B0%D1%80%D0%BE%D0%B2%22%2C%22Secs%22:55095}',
    '__ddg8_': 'eWXdswvF0juiFbUd',
    '__ddg10_': '1758523326',
    '__ddg9_': '38.107.235.96',
    '__ddg1_': 'UaTY3IH6ZXLNrTpccwuW',
    'ChipDipUID': 'G3ajMcQPcFG',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://www.chipdip.ru/',
    'Connection': 'keep-alive',
    # 'Cookie': 'ANC={%22CartSumma%22:%220%22%2C%22CartQty%22:%220%20%D1%82%D0%BE%D0%B2%D0%B0%D1%80%D0%BE%D0%B2%22%2C%22Secs%22:55095}; __ddg8_=eWXdswvF0juiFbUd; __ddg10_=1758523326; __ddg9_=38.107.235.96; __ddg1_=UaTY3IH6ZXLNrTpccwuW; ChipDipUID=G3ajMcQPcFG',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'If-Modified-Since': 'Mon, 22 Sep 2025 06:42:05 GMT',
    'If-None-Match': '"d54064dd1b3b9affef6d96f68280da79"',
    'Priority': 'u=0, i',
    # Requests doesn't support trailers
    # 'TE': 'trailers',
}

params = {
    'searchtext': 'Шлейф панели Sharp QCNW-0208FCZZ',
}

response = requests.get('https://www.chipdip.ru/search', params=params, cookies=cookies, headers=headers)



with open('request.html', 'w') as file:
    file.write(response.text)