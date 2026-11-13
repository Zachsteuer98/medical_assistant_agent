# ADR 0007 — Host the public demo on Hugging Face Spaces (Docker)

**Context.** The demo must be openable by recruiters and a few users without asking the owner,
and stay reachable. Measured footprint: ~370 MB RAM, 1.5 s startup, 104 MB index. Costs other
than OpenAI API usage should be minimal, but reachability matters more than saving a few dollars.

Alternatives considered (pricing from vendor docs and third-party comparisons, partly
contradictory; re-check before relying on it):
- **Cloud Run:** most reliably free at this load and scales to zero, but needs a Google billing
  account, budgets only alert (no hard stop), and the cold-start time is unmeasured.
- **Fly.io / Railway:** a few dollars a month; not free, billing less predictable.
- **Render free:** sleeps, likely 512 MB RAM (tight against 370 MB).

**Decision.** One Docker Space on Hugging Face (`deploy/huggingface/`):
- Docker Spaces require a paid plan (PRO, $9/month at the time of writing); the free CPU tier
  (2 vCPU, 16 GB) then sleeps after 48 hours without visitors and wakes on the next visit. An
  upgraded-hardware setting keeps it always on, at an hourly price.
- A public Space is open to anyone with the link; no permission from the owner.
- One container serves the API and the built frontend (same origin, no CORS, port 7860, runs as
  UID 1000).
- The prebuilt index is shipped inside the image, not mounted: `stage.py --build-index` ingests
  the pinned public PDFs into a fresh store and refuses to stage anything but the `public_rec`
  collection, PDFs, `.env` files, key-shaped strings or paths containing "merck". This
  supersedes ADR 0001's "never baked in" for the public corpus only (ADR 0004).
- Cost control, since every visitor question spends the owner's OpenAI money:
  1. per-client per-minute limit (existing; client IP now taken from the proxy-appended end of
     `X-Forwarded-For`, because uvicorn's `--forwarded-allow-ips "*"` trusted the spoofable
     leftmost entry);
  2. a global daily question cap (`DAILY_QUESTION_LIMIT`, default 100, in memory, UTC day);
  3. a monthly limit on a dedicated OpenAI key used only by the Space.

**Consequences.**
- Recurring cost: PRO plan plus optional always-on hardware, plus OpenAI usage (about a cent or
  less per question; worst case at the default cap about $1/day).
- The daily cap lives in memory, so a restart (including wake-up from sleep) resets it. The
  OpenAI-side key limit is the backstop. Whether that limit hard-stops or only alerts must be
  verified in the OpenAI dashboard.
- Single instance only: the in-memory limiters are not shared across replicas.
- The Space repo is public, so the source and the index of public guideline text are public.
  The OpenAI key is a Space secret; the docs do not say whether a visitor of the running app
  could extract it, so the dedicated, capped key is a requirement, not a nicety.
- To verify after the first deploy: wake-up time from sleep, that the image build fits
  Hugging Face's build limits, and the real proxy hop count (`LOG_CLIENT_CHAIN`, see README).
- A deployed image cannot be tested locally here (no Docker); CI builds the Space image on every
  push with a placeholder index.
