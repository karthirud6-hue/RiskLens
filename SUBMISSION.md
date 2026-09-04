# Razorpay AI Buildathon 2026 — Submission Draft

Draft answers for the application form. Read these over and make them sound
like you before you paste them in — I wrote them from the actual build, but
it's your name on it.

---

### Project Name / Title
RiskLens

### Track
Track 2: AI Risk Manager

### Project Objectives (What does it solve?)

RiskLens scores every transaction in real time against nine independent,
weighted risk signals — amount anomaly, transaction velocity, geo mismatch,
impossible travel between transactions, unrecognized device, high-risk
merchant category, unusual hour, newly issued card, and repeated failed
attempts — and turns that into a 0–100 risk score, a risk band, and a
fully explainable breakdown of exactly which signals fired and why.

Each band maps to a simulated compliance action a real risk system would
take: auto-approve, flag and monitor, route to manual review, or
auto-block. The goal isn't just "detect fraud" — it's detect it in a way a
compliance team can actually act on and defend, since every flagged
transaction comes with a plain-English reason, not just a number.

### GitHub Repository URL
`<paste your repo URL here once you've pushed it>`

### 5-min Pitch Video Link
`<paste your video link here>`

Suggested structure for the video (fits comfortably in 5 minutes):
1. **Problem (30s):** Fraud/risk systems that just output a score without
   explaining it aren't usable by a compliance team — a black-box "0.87"
   doesn't tell anyone what to check or how to defend a block decision.
2. **Live demo (2.5 min):** Open the dashboard, hit "Start Live Feed" and
   let transactions flow in with color-coded bands. Click a CRITICAL row to
   show the factor breakdown. Then use "Test a Custom Transaction" to
   hand-build an obvious fraud pattern live (big amount, new device, geo
   mismatch, crypto category) and show the score assemble in front of them.
3. **Architecture walkthrough (1 min):** FastAPI scoring engine + SQLite
   audit trail on the backend, React dashboard on the frontend, synthetic
   transaction generator standing in for production data. Point out that
   the scorer never sees the fraud ground-truth label — it only sees
   engineered features, same as a real system would.
4. **What's next (1 min):** hybrid rules + learned anomaly model, real
   device/IP signals, WebSocket push instead of polling, Postgres at scale.

### Build Challenges & Technical Obstacles (What issues did you face, and how did you solve them?)

**No access to real transaction data.** The obvious risk model is "train
on labeled fraud data" — I don't have any, and neither does any student
applicant. Instead of faking that, I built a synthetic transaction
generator with realistic user profiles (spending history, home country,
known devices, card age) and injected specific fraud *patterns* — velocity
bursts, impossible travel, brand-new-device-plus-large-spend, card testing
via repeated failed attempts — rather than random noise. That kept the
scoring engine honest: it's tuned against realistic attack shapes, not
against noise it could overfit to.

**Explainability vs. a black-box score.** A single numeric score is easy
to compute but useless to a compliance reviewer who has to justify a block.
I built the engine so every one of the nine signals independently
contributes points with a plain-English reason, and the top contributing
factors are always returned alongside the score — so an auto-block can
always be traced back to specific, auditable reasons, the same way my
resolveai hackathon project made SLA-escalation reasoning explicit rather
than a hidden priority number.

**Keeping "real-time" honest without overbuilding.** A full WebSocket
push pipeline was more infrastructure than a one-night build justified. I
used short-interval client polling instead (~1s) against a
`POST /api/simulate` endpoint, which gets the same live-feed feel for a
demo without the added complexity — and I documented the WebSocket
upgrade as a clear "what's next" rather than pretending polling doesn't
have that limitation.

**Choosing rule-based scoring over an opaque ML model, deliberately.** I
could have trained a classifier on the synthetic data and gotten a score
out of it, but that would have made the score *less* explainable, not
more — exactly wrong for a compliance-facing tool. The rule-based weighted
approach was the right tradeoff for this track's actual problem: I noted
where a learned anomaly-detection layer would add value (catching signals
a fixed rule set misses) as future work, on top of the explainable rules
rather than replacing them.
