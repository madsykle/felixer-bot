import requests
from bs4 import BeautifulSoup
import time

def bypass_ouo(url, depth=0):
    if depth > 5:
        return None
    
    flare_url = "http://localhost:8191/v1"
    
    # 1. GET page with FlareSolverr
    payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}
    try:
        res = requests.post(flare_url, json=payload, headers={"Content-Type": "application/json"}).json()
    except Exception:
        return None
        
    if res.get("status") != "ok": return None
        
    html = res["solution"]["response"]
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.find('form', id='form-captcha')
    
    if not form: return None
        
    post_data = ""
    for input_tag in form.find_all('input'):
        name = input_tag.get('name')
        if name and name != 'cf-turnstile-response':
            val = input_tag.get('value', '')
            post_data += f"{name}={val}&"
    
    post_data = post_data.rstrip('&')
    action = form.get('action')
    if action.startswith('/'):
        domain = "https://ouo.io" if "ouo.io" in url else "https://ouo.press"
        action = domain + action
        
    time.sleep(3)
    
    # 2. POST with FlareSolverr
    payload2 = {"cmd": "request.post", "url": action, "maxTimeout": 60000, "postData": post_data}
    try:
        res2 = requests.post(flare_url, json=payload2, headers={"Content-Type": "application/json"}).json()
    except Exception:
        return None
        
    if res2.get("status") != "ok": return None
        
    html2 = res2["solution"]["response"]
    soup2 = BeautifulSoup(html2, 'html.parser')
    form2 = soup2.find('form')
    if form2:
        action2 = form2.get('action')
        post_data2 = ""
        for input_tag in form2.find_all('input'):
            name = input_tag.get('name')
            if name:
                val = input_tag.get('value', '')
                post_data2 += f"{name}={val}&"
        post_data2 = post_data2.rstrip('&')
        
        if action2.startswith('/'):
            domain = "https://ouo.io" if "ouo.io" in res2["solution"].get("url") else "https://ouo.press"
            action2 = domain + action2
            
        payload3 = {"cmd": "request.post", "url": action2, "maxTimeout": 60000, "postData": post_data2}
        try:
            res3 = requests.post(flare_url, json=payload3, headers={"Content-Type": "application/json"}).json()
        except Exception:
            return None
            
        if res3.get("status") == "ok":
            final_url = res3['solution'].get('url')
            if "ouo.press" in final_url or "ouo.io" in final_url:
                return bypass_ouo(final_url, depth + 1)
            return final_url
        return None
    else:
        return res2["solution"].get("url")
