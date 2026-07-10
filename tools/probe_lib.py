import urllib.request, urllib.parse, re, json, time, random

BASE = "https://www.politicalcompass.org/test/en"
HDRS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": BASE, "Content-Type": "application/x-www-form-urlencoded",
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
opener = urllib.request.build_opener(NoRedirect)

QS = json.load(open("questions.json"))
PAGES = {}
for q in QS: PAGES.setdefault(q["page"], []).append(q["name"])

def post(form):
    """POST form; return ('redirect', location) or ('page', html)."""
    req = urllib.request.Request(BASE, data=urllib.parse.urlencode(form).encode(), headers=HDRS)
    try:
        with opener.open(req, timeout=30) as r:
            return "page", r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307): return "redirect", e.headers.get("Location")
        raise

def coords(loc):
    m = re.search(r'ec=(-?[\d.]+)&soc=(-?[\d.]+)', loc)
    return (float(m.group(1)), float(m.group(2))) if m else None

def one_shot(answers):
    form = {"page": "7", "carried_ec": "0", "carried_soc": "0", "populated": ""}
    form.update({k: str(v) for k, v in answers.items()})
    kind, out = post(form)
    assert kind == "redirect", f"expected redirect, got page: {out[:200]}"
    return coords(out)

def walk(answers):
    carried = {"carried_ec": "", "carried_soc": "", "populated": ""}
    for pg in range(1, 7):
        form = {"page": str(pg + 1), **carried}
        for name in PAGES[pg]: form[name] = str(answers[name])
        kind, out = post(form)
        time.sleep(0.4)
        if kind == "redirect": return coords(out)
        hidden = dict(re.findall(r'<input name="([^"]+)" type="hidden" value="([^"]*)"', out))
        carried = {k: hidden.get(k, "") for k in ("carried_ec", "carried_soc", "populated")}
    return None
