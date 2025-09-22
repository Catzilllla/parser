import requests

cookies = {
    '90a27748f029670aa3b56d4ff1180f2d': 'b24d68177cd0c1a670d56b37fdde4c1c',
    'supportOnlineTalkID': 'mS8PChH1vpl4cKALyuVvhEPqBLRckaZG',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://vce-o-printere.ru/komplektuyuschie-zip-dlya-printera/zip-hp/raznoe-hp/hp-jc0700020a-lcd-displey-jc0700020a-lcd-displey-zapchasti-panel-upravleniya-jc0700020a-dlya-modeley-lj-mfp-m433.html',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://vce-o-printere.ru',
    'Connection': 'keep-alive',
    # 'Cookie': '90a27748f029670aa3b56d4ff1180f2d=b24d68177cd0c1a670d56b37fdde4c1c; supportOnlineTalkID=mS8PChH1vpl4cKALyuVvhEPqBLRckaZG',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Priority': 'u=0, i',
}

data = {
    'setsearchdata': '1',
    'search_type': 'all',
    'category_id': '0',
    'search': 'JC07-00020A',
    'acategory_id': '0',
}

response = requests.post('https://vce-o-printere.ru/search/result.html', cookies=cookies, headers=headers, data=data)


with open('request.html', 'w') as file:
    file.write(response.text)