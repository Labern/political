import json, time, re
from probe_lib import *

def page_contrib(pg, answers):
    """POST page pg with given answers (dict name->v), carried=0. Return raw int (ec,soc)."""
    form = {"page": str(pg), "carried_ec": "0", "carried_soc": "0", "populated": ""}
    form.update({k: str(v) for k, v in answers.items()})
    kind, out = post(form)
    if kind == "redirect":  # page 6 -> results; coords = raw/8, raw/19.5 rounded 2dp
        ec, soc = coords(out)
        rec, rsoc = ec * 8, soc * 19.5
        assert abs(rec - round(rec)) < 0.11 and abs(rsoc - round(rsoc)) < 0.11, (ec, soc, rec, rsoc)
        return round(rec), round(rsoc)
    hidden = dict(re.findall(r'<input name="([^"]+)" type="hidden" value="([^"]*)"', out))
    return int(hidden["carried_ec"]), int(hidden["carried_soc"])

weights = {}   # name -> [[ec,soc] x4 options] absolute per-option raw weights (rel. unknown const per q)
bases = {}
t0 = time.time(); n = 0
for pg in sorted(PAGES):
    names = PAGES[pg]
    zeros = {m: 0 for m in names}
    bases[pg] = page_contrib(pg, zeros); n += 1; time.sleep(0.35)
    for name in names:
        weights[name] = [None, None, None, None]
        for v in (1, 2, 3):
            c = page_contrib(pg, {**zeros, name: v}); n += 1; time.sleep(0.35)
            weights[name][v] = [c[0] - bases[pg][0], c[1] - bases[pg][1]]  # delta vs option-0
        weights[name][0] = [0, 0]
    print(f"page {pg} done ({n} reqs, {time.time()-t0:.0f}s) base={bases[pg]}", flush=True)

json.dump({"bases": {str(k): v for k, v in bases.items()}, "deltas": weights},
          open("weights.json", "w"), indent=1)

# validation: 4 random sets, predict vs actual one-shot
import random
ok = True
for seed in (7, 123, 999, 2024):
    random.seed(seed)
    ans = {q["name"]: random.randint(0, 3) for q in QS}
    rec = sum(b[0] for b in bases.values()) + sum(weights[k][v][0] for k, v in ans.items())
    rsoc = sum(b[1] for b in bases.values()) + sum(weights[k][v][1] for k, v in ans.items())
    pred = (round(rec / 8.0, 2), round(rsoc / 19.5, 2))
    act = one_shot(ans); time.sleep(0.35)
    match = pred == act
    ok &= match
    print(f"seed {seed}: predicted {pred} actual {act} {'MATCH' if match else 'MISMATCH'}", flush=True)
print("ALL VALIDATED" if ok else "VALIDATION FAILED", flush=True)
