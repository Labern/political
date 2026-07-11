# KNOWLEDGE — POLITICAL DISCUSSION

Reference doc, written to be lifted into future projects. Two independent halves:
**§1 Logic** (serverless two-client realtime patterns, exact scoring replication) and
**§2 Design** (the fun rainbow-sticker/comic recipe). Live app:
https://labern.github.io/political/ · repo `Labern/political`.

---

## §1 LOGIC — reusable engineering patterns

### 1.1 Serverless two-person realtime sync (no accounts, no backend)
- **Transport:** MQTT over WSS on public brokers, mqtt.js v5 vendored
  (`vendor/mqtt.min.js`, global `mqtt`). Broker list EMQX `:8084` → HiveMQ `:8884`
  → Mosquitto `test.mosquitto.org:8081`, tried in a **fixed deterministic order,
  never a race** — see §1.6 for why (this superseded an earlier "keep whichever
  connects fastest" approach that caused a real data-visibility incident).
- **State model:** one **retained** message per person per room:
  topic `polduo1/<roomId>/<role>`, payload
  `{v, self, role, ans:{key:[value,ts]}, com:{key:[text,ts]}, typing:[key,ts], done, updated}`.
  Retained = the broker stores the latest doc per topic, so a freshly-opened client
  gets both people's full state instantly on subscribe. QoS 1, `retain:true`.
- **Each client writes ONLY its own topic; subscribes to both.** Subscribing to your
  own topic is the cloud-recovery path (your answers come back on a storage-less
  device). Tag payloads with a random per-pageload `self` id and ignore your own
  echoes — otherwise incoming echoes re-render screens out from under the user.
- **Merge rule (the no-loss core):** per-key newest-timestamp-wins, purely additive —
  `if(!dst[k] || src[k].ts > dst[k].ts) dst[k]=src[k]`. Never replace whole maps.
  This makes every path self-healing: stale retained docs, second devices on the
  same link, broker wipes, offline edits — all converge without losing a key.
- **Persistence layers:** localStorage mirror on every mutation (key
  `polduo:<roomId>`) + the retained cloud doc. Either alone restores everything.
  On `visibilitychange → visible`: reconnect + republish (heals broker restarts,
  and matters in in-app browsers where JS freezes in background).
- **Live typing:** comment text rides the same retained doc, republished with a
  ~280 ms trailing throttle; `typing:[key, ts]` shows "X is thinking…" while
  `now - ts < 5 s`. A 1.5 s interval refreshes just that line (never full render).
- **Re-render vs input focus:** incoming partner messages re-render the screen; a
  focused `<textarea>` must survive. Snapshot value/focus/selection before
  `innerHTML` rebuild, restore after. Alternatively update only the partner nodes.
- **Screen gating:** message-driven renders must check a `VIEW` flag and only
  re-render "live" screens (flow/results) — otherwise pushes yank users off
  share/welcome/setup screens. (Bug found in testing; the `self`-tag alone wasn't
  enough because a *partner* message can arrive on any screen.)

### 1.2 Identity via personal links (zero-login two-user apps)
- Room = random id; each person gets `#r/<roomId>/<ROLE>`. The link IS the account:
  role, room, and resume all derive from it. Keep links pinned in the chat thread —
  in-app popup browsers (WhatsApp) may drop storage, but link + retained cloud doc
  restores everything (tested: full `localStorage.clear()` + reload → complete state
  back in ~3 s).
- **Role guard:** if localStorage says you're role A and the opened link is role B,
  interpose a "whose link is this?" screen. Prevents partners corrupting each
  other's docs via a mistapped link (and same-device testing hits it constantly).
- Hash routing with `history.replaceState` (no history spam): `#r/<r>/<role>/q12`
  per question, `/done` on results so back/reload lands correctly.

### 1.3 Replicating a third-party scorer exactly (politicalcompass.org)
- The test is 6 form pages POSTing to `/test/en`; running score travels in hidden
  `carried_ec`/`carried_soc` fields (integers) — the server is **stateless**, so
  the whole thing is probeable one page at a time with `carried=0`.
- **Derivation method (generalizes to any stateless form scorer):** baseline POST
  (all option-0) per page, then vary one field/option at a time and read the delta
  from the next page's carried values (~190 requests total, 0.35 s spacing). Weights
  are integers → measurements are exact, no rounding accumulation.
- Formula recovered: `raw = Σ weights`; `ec = round±(raw_ec/8, 2)`,
  `soc = round±(raw_soc/19.5, 2)` where `round±` is **half-away-from-zero**
  (NOT JS `Math.round`, NOT Python banker's `round`) — pinned by finding an answer
  set summing to raw −17 (−2.125 → −2.13).
- **Official routing without CORS:** a cross-origin form POST with top-level
  navigation is always allowed. POST `page=7, carried_ec=0, carried_soc=0,
  populated=` + all 62 `name=value` → server 302s to
  `/analysis2?ec=…&soc=…` (their official results page, deep-linkable by params).
  Verified: single POST ≡ full 6-page walk ≡ our local math, exact, incl. a live
  click-through parity test.
- Derivation scripts preserved in `tools/` (walker.py = scrape, probe_weights.py =
  weights + validation, probe_lib.py = shared). Rerun if the site ever changes;
  regenerate `data.js`. **Never hand-edit `data.js`.**

### 1.4 The never-lose-progress discipline (standing user principle, all apps)
- Additive-only storage + wire schemas; hydrate old state over defaults; never clear
  storage in code; count progress against the CURRENT schema by name, not key count;
  clamp indices arriving from URLs/persisted state.
- Upgrade test before every schema-touching deploy: old-build fixture session loaded
  on the new build, plus one-old-one-new client pairing in the same room.
- Real bug this caught here: a finished-session `/done` link opened on a
  storage-evicted device crashed the renderer before cloud state arrived
  (`Q[62]` indexing) — clamp fixed; results gate now name-based so even a changed
  question list can't brick the endgame.

### 1.5 Testing patterns that caught real bugs
- Two live browser tabs as the two clients, driving real UI + JS injection; a
  same-profile pair shares localStorage → expect the role guard (that's the guard
  working, not a bug).
- Bugs caught this way: own-echo yanking share/welcome screens; results hash
  colliding with question routing after returning from the official site;
  preflight-dead REST backends (jsonblob 404s OPTIONS, kvdb needs email
  verification, extendsclass 500s OPTIONS → why MQTT won).

### 1.6 The multi-broker incident — read before touching sync (paid in blood)
The single hardest lesson of the project. **Retained state on EMQX, HiveMQ and
Mosquitto are THREE SEPARATE STORES** — a message retained on one is invisible on
the others. They are reachability alternates, NOT interchangeable mirrors.
- **What broke:** a version that connected to all brokers in parallel and kept
  whichever answered *fastest*. Sounds robust; was a production incident. Two
  people's sessions could silently land on different, mutually-blind brokers —
  each showing "synced" while seeing none of the other's answers/typing. The user
  reported it as "you just made me lose access to all her answers" and "it just
  says synced. Not online." Nothing was ever deleted — it was being read from the
  wrong place.
- **Fix, two parts:** (1) try brokers in a **fixed order on every device**, so
  everyone converges on the same primary. (2) **`sweepOtherBrokers()`** — on every
  connect, briefly (~3 s) also subscribe on the non-primary brokers and merge in
  anything found (same newest-wins merge), then close those probes. This is the
  self-healing layer that *recovers* a room already split across brokers, and is
  what got "her" answers back with zero manual steps. Keep the sweep even though
  the deterministic order makes splits rare — it converts the whole bug class into
  a non-issue. Verified by planting state on a non-primary broker and confirming a
  fresh connect recovers it in <1 s.
- **Presence needs the SAME resilience — and it was forgotten once.** Online status
  lives on a **separate topic** `polduo1/<room>/<role>/presence` (never mixed with
  answer data). It uses MQTT **Last Will (LWT)**: register `{online:false}` at
  connect so the broker auto-publishes offline on an unclean drop (tab killed,
  network dies) — no polling. But the first cut only subscribed presence on the
  *primary* connection, so after the broker-mismatch fix answers recovered via the
  sweep while presence stayed stuck on "synced, never Online." Fix: route presence
  through the sweep too.
- **Presence republish bug (caught in review):** publishing `{online:true}` ONCE at
  connect makes any staleness-timeout check meaningless — `lastSeen` never advances,
  so a genuinely-present partner flips to "offline" after the timeout. Must
  **re-publish presence on the periodic heartbeat** (~every 10 s) so "last seen"
  means "confirmed recently", plus an explicit `{online:false/true}` on
  tab-hide/show for an instant courtesy signal on top of LWT.
- **Newest-wins timestamp guard on presence** so a stale sweep result can't override
  a fresher signal from the primary.

### 1.7 Process invariant — "done" means the user can see it LIVE
Not "verified locally", not "committed", not "pushed". For this app the finish line
is **deployed AND confirmed serving on the real URL** (`labern.github.io/political`).
Cause of a real "it isn't working" round: several features were built + locally
tested but not deployed, so the user's live site still showed the old version. The
deploy-and-confirm-live step is part of every task, not an afterthought; never
report "done"/"fixed" for anything the user can't yet see. (Standard deploy: push
to `main`; Pages serves repo root; poll `curl` for a marker string in the live HTML
before declaring it live — GitHub Pages lags the push by ~30–90 s.)

---

## §2 DESIGN — the rainbow-sticker / comic recipe ("for fun" skin)

Origin: two hand-drawn sticker images (kawaii lemon with a face; chibi girl blowing
bubblegum), both on bold textured rainbow arcs with thick white sticker outlines
(`assets/lemon.jpg`, `assets/sol.jpg`). User verdict: "Design is INSANE. Masterpiece."

### 2.1 Tokens (all theming is CSS custom properties)
```css
--paper:#fff9e8; --card:#fff; --ink:#1c1c1c; --faint:#6b6357;
--rb-red:#e8433f; --rb-orange:#f2792f; --rb-yellow:#f4c93c;
--rb-green:#57a94e; --rb-blue:#3a7de0; --rb-purple:#6b3fbf;
--rainbow:linear-gradient(90deg, red→purple tokens);
--hard:4px 5px 0 rgba(28,28,28,.9);  --hard-sm:3px 3px 0 rgba(28,28,28,.85);
--font:"Comic Sans MS","Comic Sans","Chalkboard SE","Marker Felt","Segoe Print",cursive;
```
(Chalkboard SE is the iOS fallback — iPhones have no Comic Sans.)

### 2.2 The backdrop: concentric rainbow arcs + paper noise
```css
body::before{position:fixed;inset:0;z-index:-2;background:
  radial-gradient(150vmax 150vmax at 50% 130%,
    purple 0 19vmax, blue 19vmax 31vmax, green 31vmax 43vmax,
    yellow 43vmax 55vmax, orange 55vmax 67vmax, red 67vmax 82vmax, paper 82vmax)}
body::after{/* inline SVG feTurbulence data-URI, opacity:.07 */}
```
Order matters: purple innermost at the bottom, red outermost — matches the stickers.

### 2.3 Sticker components
- **Cards/buttons:** white bg, `3px solid var(--ink)`, big radius (16–22px),
  **hard offset shadow** (`--hard`). Press effect = `translate(2px,2px)` + shadow
  collapse to 1px (feels physically clicky). ~~Alternating ±0.4° rotation.~~
  **Superseded 2026-07-11:** the tilt is GONE — see §2.4.
- **Readability rule (learned from user feedback):** nothing sits bare on the
  rainbow. Body text goes in white sticker panels; small floating text gets
  translucent white pills (`rgba(255,255,255,.88)`, radius 99px). Generous vertical
  margins (~18px between blocks) — don't squeeze.
- **Comic headline:** white text + `-webkit-text-stroke:1.6px ink` +
  `text-shadow:3px 3px 0 ink`. ~~Slow ±1.2° wobble keyframes.~~ **Wobble removed
  2026-07-11** (see §2.4).
- **Avatars:** real images, `border-radius:50%`, ink border + `0 0 0 4px #fff`
  sticker ring + hard shadow, gentle bob animation (offset delays per character);
  `object-position` tuned per image to center the face.
- **Chips:** pill + ink border; answer scale colored red→orange→light/dark green;
  "waiting" chips = dashed border + italic.
- **Effects:** rainbow gradient sliding on primary buttons/progress bar (`background
  -size:250%` + linear keyframes); emoji sparkle bursts on reveal; bordered confetti
  rain on completion; `#toast` = sticker pill sliding up from bottom.
- Compass chart: SVG, pastel quadrants, avatar-image dots with white ring + ink
  stroke, dashed purple line between the two people + "you two are X units apart 💞".

### 2.4 Spirit
Cartoonish and crazy but legible: hard shadows everywhere, emoji as punctuation
(🍋🫧💌✨), playful microcopy ("interesting… time to talk 👀"). One page, no build
step, no external fonts/CDNs.
- **Tilt calibration (2026-07-11):** an earlier version tilted nearly *everything*
  — cards (alternating), wordmark, animated h1 wobble, section chips, the
  proposition card, both side cards. The user's read: **"overdone… remove it."**
  Now everything is level; the sticker feel comes entirely from **hard offset
  shadows + thick ink borders + rainbow**, which is plenty. Lesson: the tilt is a
  seasoning, not the dish — one or two elements at most, and it accumulates into
  chaos fast when many stacked elements each carry their own angle. Kept: the
  gentle avatar float (`bob`) and confetti spin. (The user separately called an
  earlier, less-tilted state a "masterpiece" — the sticker shadows/borders are what
  he loved, not the slant.)

### 2.5 Other UX decisions worth keeping
- **"Discuss on WhatsApp" pre-fills context.** Per-question button opens
  `wa.me/?text=` with a minimal recap: `Q<n> — "<question>"` then each person's
  answer with their emoji. The person's own take is their *next* manual message.
  Works in the WhatsApp in-app browser + native app; needs no reply-parsing (this
  app can't read WhatsApp, only seed a draft).
- **Mobile 100%-width:** the header's right-side pill cluster (links + Online) had
  no wrap and pushed ~28px past the column at phone width → sideways scroll / page
  not locking to viewport. Fix: `flex-wrap:wrap` on the header AND that cluster,
  plus `html,body{width:100%;max-width:100%;overflow-x:hidden}`. Diagnose mobile
  overflow without true device emulation by temporarily shrinking `#app` to ~360px
  and listing children whose `getBoundingClientRect().right` exceeds it.
- **Degree-aware agreement (DESIGNED, not yet built — user said "No" for now,
  2026-07-11).** The per-question verdict currently only checks *exact equality*, so
  "Agree vs Strongly agree" (same side!) reads identical to a real clash. Planned
  5-state, side-first-then-distance verdict (exact / same-side-different-degree /
  opposite-adjacent / opposite-clear / polar), color-coded, matching the taxonomy
  already live in the results-page `computeAgreementStats()`. Revisit only if asked.
