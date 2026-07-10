# political — Political Compass for two

A single-page web app (GitHub Pages: https://labern.github.io/political/) that lets two
people — Lemon 🍋 (him) and Girl 🎀 (her) — take the politicalcompass.org test together
from separate phones, one proposition at a time, revealing each other's answer only after
both have picked, then discussing on WhatsApp. At the end each gets their **official**
result, computed by the real politicalcompass.org.

## Architecture (all static, no backend of our own)

- `index.html` — the whole app: UI, sync, scoring, routing. Design tokens in `:root` CSS
  custom properties (themeable by token swap only — never hardcode colors in rules).
- `data.js` — `PC_DATA`: all 62 propositions (exact text from politicalcompass.org),
  per-option integer weight deltas `w[option] = [Δec, Δsoc]`, `BASE = [0, -85]`,
  divisors `[8, 19.5]`, the 6 official page intros.
- `vendor/mqtt.min.js` — mqtt.js v5 browser bundle (vendored, no CDN dependency).
- `tools/` — the Python scripts that derived and validated `data.js` from the live site.

## The scoring contract (do not hand-edit)

`data.js` was **empirically derived** from politicalcompass.org (2026-07) and validated
exact on 5 random answer sets:

```
raw   = BASE + Σ w[q][answer]          (integers, per axis)
ec    = roundHalfAwayFromZero(raw_ec / 8,    2)
soc   = roundHalfAwayFromZero(raw_soc / 19.5, 2)
```

- The site's own rounding is half-AWAY-FROM-ZERO (not JS `Math.round`, not Python
  `round`). Keep the `rhalf` implementation as is.
- "Official result" buttons build a hidden form POST to
  `https://www.politicalcompass.org/test/en` with `page=7`, `carried_ec=0`,
  `carried_soc=0`, plus all 62 `name=value` answers → the server 302s to
  `/analysis2?ec=…&soc=…`. Validated equivalent to taking the test page by page.
- To re-derive after a site change: run `tools/probe_weights.py` (needs
  `tools/probe_lib.py` + a fresh `questions.json` from `tools/walker.py`). ~190 polite
  requests. Regenerate `data.js` with `tools/gen_data.py`.

## Sync model (two phones, no accounts)

- MQTT over WSS, public brokers with failover: `broker.emqx.io:8084` → `broker.hivemq.com:8884`.
- Topic `polduo1/<roomId>/<L|G>`, **retained** JSON `{v:1, role, ans:{q:[val,ts]}, done, updated}`.
- Each client publishes only its OWN topic; subscribes to both (own = cloud recovery).
- Merge is per-question newest-timestamp-wins (`mergeInto`) — answers can never be lost;
  a wiped broker heals from localStorage on next publish and vice versa.
- Personal links `#r/<roomId>/<L|G>` are the durable resume mechanism (WhatsApp popup
  browsers may drop localStorage; the link + retained state restores everything).
- Reveal rule: partner's answer for a question is shown only once you've answered it.

## Working on this project

- **Use sub-agents liberally**: fan out independent investigations (e.g. re-probing the
  live site, broker health checks, cross-browser quirks) and noisy searches to
  sub-agents in parallel; keep the main context for decisions and edits.
- Test flow: serve locally (`python3 -m http.server`), open two browser profiles/tabs —
  one `#r/test/L`, one `#r/test/G` — and step through answer → reveal → results.
- Deploys: push to `main`; GitHub Pages serves the repo root. No build step.
