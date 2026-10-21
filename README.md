# 🌿 ForzoASK – AI content assistant (Forzo Techlabs Marketing)

ForzoASK writes first drafts of marketing content (LinkedIn posts for EPR, Carbalyze/PCF and Carboventory, blog promotions, blog outlines, outreach notes) from a markdown knowledge base. A person always reviews, edits and copies the draft. The app remembers what was posted so new drafts don't repeat it.

**Pilot setup: ₹0** – Streamlit Community Cloud + Gemini API free tier + GitHub.

---

## How it works

```
kb/*.md  ──►  prompt (guidelines + chosen knowledge + recent posts)  ──►  Gemini  ──►  2–3 drafts
                                                                              │
     history (GitHub "history" branch)  ◄──  "Mark as used"  ◄──  person reviews, edits, copies
```

| File | What it does |
|---|---|
| `app.py` | The Streamlit app: login, create, history, knowledge base, help |
| `auth.py` | Login with one username/password set in Streamlit secrets |
| `kb_loader.py` | Reads every `.md` under `kb/` |
| `llm.py` | The only file that talks to the AI model (swap providers here) |
| `history.py` | Saves used content; warns when a draft repeats an earlier post |
| `prompts/` | One template per content type + `_system.md` rules |
| `kb/` | The knowledge base (see below) |
| `data/history_seed.json` | Page posts published before the app (Oct 2026) |
| `scripts/scrape_site.py` | Refreshes knowledge from our websites (run locally) |

## Knowledge base (`kb/`)

| Folder | Content |
|---|---|
| `guidelines.md` | Tone, audience, CTAs and the **"Never write"** list. Sent with every request. |
| `carbalyze/` | PCF product overview, plans |
| `epr/` | Packaging Intelligence product + dated EPR regulatory facts |
| `carboventory/` | Asset-reuse product |
| `company/` | Forzo Techlabs overview |
| `blogs/` | Blog summaries + `_catalog.md` of all posts |
| `linkedin/` | House style notes |

**Add knowledge:** create a `.md` file in the right folder and push. Start it with a header (copy any existing file):

```
---
title: Short title
type: product | blog | regulatory | company | style
product: carbalyze | epr | carboventory | ftl
url: https://...
retrieved: 2026-10-21
---
```

Folders starting with `_` (e.g. `kb/_scraped/`) are ignored – use them for raw scrapes awaiting review.

**Refresh from the websites (optional):**
```bash
pip install requests beautifulsoup4 markdownify
python scripts/scrape_site.py --blogs 20
# review kb/_scraped/, move/merge good content into kb/, commit
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then edit it
streamlit run app.py
```
Without `GEMINI_API_KEY` the app runs in **demo mode** (placeholder drafts). Without `GITHUB_TOKEN`, history is saved to a local file.

## Deploy (Streamlit Community Cloud)

1. **GitHub repo:** create `forzoask` under the **FTL organisation account** (private recommended) and push this folder.
2. **Gemini key:** https://aistudio.google.com → *Get API key* (free tier). Free-tier prompts may be used by Google to improve its products, so the knowledge base holds **public information only**.
3. **GitHub token for history:** GitHub → Settings → Developer settings → *Fine-grained tokens* → repository access: only `forzoask` → permission **Contents: Read and write**. The app creates a `history` branch on first save (separate from `main`, so saving never redeploys the app).
4. **Deploy:** https://share.streamlit.io → *Create app* → pick the repo, branch `main`, file `app.py`.
5. **Secrets:** app → *Settings → Secrets* → paste the content of `secrets.toml.example` with real values.
6. **Sharing:** set the app to **public** (the login screen protects it). Anyone without a username/password sees only the sign-in form.

Change the login: edit `APP_USERNAME` / `APP_PASSWORD` in Secrets and save.

**Time tracking (automatic):** when a draft is marked as used, the app stores the AI writing time, the total time from the first *Generate* click to *Mark as used*, how many times *Generate* was clicked, and how much the person edited the draft. See **Content history** for averages and a CSV download.

## Good to know

- Free Streamlit apps can go to sleep when nobody uses them for a while; waking one takes a short wait (a "wake up" button appears).
- Free Gemini tier has per-minute and per-day limits; the app retries and shows a clear message if hit.
- One shared login, with a 60-second lockout after 5 wrong tries (per browser session). Fine for a pilot; switch to company Google/Microsoft login for production.
- To change model or provider, edit `GEMINI_MODEL` in secrets or `llm.py`.

## Roadmap (add only when the pilot proves value)

1. Scheduled scraping of the websites into `kb/_scraped/` for review
2. Live web search for regulatory news, with sources
3. Optional automated claims check
4. Embeddings search when the knowledge base grows large
5. LinkedIn scheduling and engagement tracking
6. Sales / outreach module for the wider team
