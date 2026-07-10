# 🍋 two of us 🎀 — the Political Compass, together

Take [the Political Compass test](https://www.politicalcompass.org/test) as a couple,
from two phones, one proposition at a time.

- Each of you picks an answer — **only then** is the other's revealed.
- A "Return to WhatsApp" button after every reveal, for the arguing part. 💬
- Answers save automatically (to the phone *and* to your shared room) — your personal
  link in the chat always resumes exactly where you left off.
- At the end: both dots on one compass, plus each person's **official result** rendered
  by the real politicalcompass.org from your actual answers.

**Live:** https://labern.github.io/political/

No accounts, no backend of our own: static page on GitHub Pages, realtime sync via
public MQTT brokers (retained messages), scoring bit-identical to the official site
(empirically derived + validated — see `CLAUDE.md`).

Propositions and scoring © [politicalcompass.org](https://www.politicalcompass.org) —
this is a personal two-player companion that routes official scoring through their site.
