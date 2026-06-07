import requests
import json
from bs4 import BeautifulSoup
import re

FLARESOLVERR_URL = "http://localhost:8191/v1"

def _flaresolverr_get(url: str):
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000
    }
    res = requests.post(FLARESOLVERR_URL, json=payload, headers={"Content-Type": "application/json"})
    res.raise_for_status()
    data = res.json()
    if data.get("status") == "ok" and "solution" in data:
        return data["solution"]["response"]
    else:
        raise Exception(f"FlareSolverr error: {data}")

def search_psa(query: str):
    url = f"https://psa.wf/?s={requests.utils.quote(query)}"
    html = _flaresolverr_get(url)
    soup = BeautifulSoup(html, "html.parser")
    
    results = []
    # PSA.wf uses <article> tags or .post-list
    for article in soup.select("article"):
        title_tag = article.select_one(".entry-title a, .post-title a")
        if not title_tag:
            continue
        title = title_tag.text.strip()
        link = title_tag.get("href")
        if link:
            results.append({"title": title, "link": link})
            
    return results

def get_psa_details(url: str):
    html = _flaresolverr_get(url)
    soup = BeautifulSoup(html, "html.parser")
    qualities = {}
    
    # 1. TV Show format (.box.download)
    boxes = soup.select(".box.download")
    for box in boxes:
        box_html = str(box)
        for seg in box_html.split("<b>"):
            if "</b>" not in seg:
                continue
            head, rest = seg.split("</b>", 1)
            qt = re.sub(r"<[^>]+>", "", head).strip()
            
            links = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', rest)
            valid_links = []
            for href, text in links:
                if "http" in href:
                    valid_links.append({"name": text.strip(), "url": href.strip()})
                    
            if valid_links and qt:
                if qt not in qualities:
                    qualities[qt] = []
                qualities[qt].extend(valid_links)

    # 2. Movie format (<p><strong>Title</strong></p> followed by sp-wrap -> Download)
    if not qualities:
        # Find all <p><strong>
        for p in soup.select("p"):
            strong = p.select_one("strong")
            if not strong:
                continue
            title_text = strong.text.strip()
            if not title_text or "Size:" in title_text or "Source" in title_text or "Sample" in title_text:
                continue
                
            # It's a release title. Now look for the next sp-wrap that contains "Download"
            curr = p.find_next_sibling()
            valid_links = []
            while curr:
                if curr.name == "p" and curr.select_one("strong"):
                    # Found another title, stop looking
                    break
                if curr.name == "div" and "sp-wrap" in curr.get("class", []):
                    head = curr.select_one(".sp-head")
                    if head and "Download" in head.text:
                        # Extract links from the body
                        for a in curr.select("a"):
                            href = a.get("href")
                            text = a.text.strip() or "Link"
                            if href and "http" in href:
                                valid_links.append({"name": text, "url": href})
                        break
                curr = curr.find_next_sibling()
                
            if valid_links:
                # Remove strikethrough characters (̶) used for dead links
                title_text = title_text.replace("̶", "").strip()
                if title_text not in qualities:
                    qualities[title_text] = []
                qualities[title_text].extend(valid_links)
                
    # 3. Old TV Show format (sp-wrap where sp-head is the title)
    if not qualities:
        for sp_wrap in soup.select(".sp-wrap"):
            head = sp_wrap.select_one(".sp-head")
            if not head:
                continue
            title_text = head.text.strip()
            # If the header doesn't say "Info" or "Download" and isn't empty, it's likely a title
            if title_text and title_text.lower() not in ["info", "download", "screenshots"]:
                # Check if this sp-wrap contains other sp-wraps (it's just a container)
                body = sp_wrap.select_one(".sp-body")
                if body and body.select(".sp-wrap"):
                    continue
                    
                valid_links = []
                for a in sp_wrap.select(".sp-body a"):
                    href = a.get("href")
                    text = a.text.strip() or "Link"
                    if href and "http" in href:
                        valid_links.append({"name": text, "url": href})
                if valid_links:
                    title_text = title_text.replace("̶", "").strip()
                    if title_text not in qualities:
                        qualities[title_text] = []
                    qualities[title_text].extend(valid_links)
                    
    return {"qualities": qualities}

if __name__ == "__main__":
    print("Searching for 'The Boys'...")
    results = search_psa("The Boys")
    print(json.dumps(results, indent=2))
    
    if results:
        print("\nFetching details for the first result...")
        details = get_psa_details(results[0]["link"])
        print(json.dumps(details, indent=2))
