import urllib.request, urllib.parse, re, json, html as h, time, sys

BASE = "https://www.politicalcompass.org/test/en"
HDRS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": BASE,
    "Content-Type": "application/x-www-form-urlencoded",
}

def fetch(data=None, url=BASE):
    req = urllib.request.Request(url, data=data.encode() if data else None, headers=HDRS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode('utf-8', 'replace')

def parse(page_html):
    hidden = dict(re.findall(r'<input name="([^"]+)" type="hidden" value="([^"]*)"', page_html))
    qs = []
    for chunk in page_html.split('<fieldset')[1:]:
        m = re.search(r'<legend[^>]*>\s*(.*?)\s*</legend>', chunk, re.S)
        n = re.search(r'name="([a-zA-Z0-9_]+)" type="radio"', chunk)
        if m and n:
            text = h.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', m.group(1)))).strip()
            qs.append({"name": n.group(1), "text": text})
    pg = re.search(r'Page (\d) of 6', page_html)
    return hidden, qs, pg.group(1) if pg else '?'

url, ph = fetch(url=BASE + "?page=1")
all_q = []
for step in range(6):
    hidden, qs, pg = parse(ph)
    print(f"== Page {pg}: {len(qs)} questions | hidden: {hidden}")
    for q in qs: q["page"] = int(pg); all_q.append(q)
    form = {k: v for k, v in hidden.items()}
    form["page"] = str(int(pg) + 1)          # next page requested
    for q in qs: form[q["name"]] = "0"       # all Strongly disagree
    time.sleep(0.6)
    url, ph = fetch(urllib.parse.urlencode(form))
    if step == 5:
        open("results.html", "w").write(ph)
        print("FINAL URL:", url)
        for pat in [r'[Ee]conomic[^<]*?(-?\d+\.?\d*)', r'ec\s*=\s*(-?\d+\.?\d*)', r'ec=(-?\d+\.\d+)', r'soc=(-?\d+\.\d+)']:
            mm = re.findall(pat, ph)
            if mm: print("pattern", pat, "->", mm[:6])

json.dump(all_q, open("questions.json", "w"), indent=1)
print(f"TOTAL: {len(all_q)} questions -> questions.json")
