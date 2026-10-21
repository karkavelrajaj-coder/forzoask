"""ForzoASK – AI content assistant for the Forzo Techlabs marketing team.

Flow: sign in → pick content type → topic/notes → generate drafts from the
markdown knowledge base → review, edit, copy → "Mark as used" (saved to history,
so future drafts avoid repeating it).
"""
from __future__ import annotations

import time
from difflib import SequenceMatcher
from pathlib import Path

import streamlit as st

import auth
import history
import kb_loader
import llm

ROOT = Path(__file__).parent
PROMPTS_DIR = ROOT / "prompts"
APP_NAME = "ForzoASK"
TONES = ["Professional and practical", "Conversational", "Direct and bold", "Educational / explainer"]

st.set_page_config(page_title=f"{APP_NAME} · Marketing", page_icon="🌿", layout="wide")

# ------------------------------------------------------------------ styling
st.markdown(
    """
    <style>
    :root { --g900:#0b3d2e; --g700:#166534; --g600:#16a34a; --g100:#dcfce7; --g50:#f0fdf4; }
    .block-container { padding-top: 2rem; max-width: 1200px; }
    .fa-header { background: linear-gradient(120deg, var(--g900) 0%, var(--g700) 55%, var(--g600) 100%);
                 color: #fff; padding: 1.2rem 1.6rem; border-radius: 14px; margin-bottom: 1.2rem; }
    .fa-header h1 { color:#fff; font-size: 1.7rem; margin: 0; letter-spacing: .3px; }
    .fa-header p { color: #d1fae5; margin: .2rem 0 0 0; font-size: .95rem; }
    .login-card { background: var(--g50); border: 1px solid var(--g100); border-radius: 14px; padding: 1.2rem 1.4rem; }
    .pill { display:inline-block; background: var(--g100); color: var(--g900); border-radius: 999px;
            padding: .1rem .6rem; font-size: .78rem; margin-right: .3rem; }
    .warn-box { background:#fffbeb; border-left: 4px solid #f59e0b; padding:.6rem .8rem; border-radius:8px; }
    section[data-testid="stSidebar"] { background: var(--g50); }
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {
        background: var(--g700); border-color: var(--g700); }
    div.stButton > button[kind="primary"]:hover { background: var(--g600); border-color: var(--g600); }
    </style>
    """,
    unsafe_allow_html=True,
)


def header(subtitle: str = "AI content assistant for Carbalyze · Packaging Intelligence (EPR) · Carboventory") -> None:
    st.markdown(f"<div class='fa-header'><h1>🌿 {APP_NAME}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ helpers
def secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


@st.cache_data(ttl=300)
def load_kb_cached():
    return kb_loader.load_kb()


@st.cache_data
def load_prompts() -> dict:
    prompts = {}
    for file in sorted(PROMPTS_DIR.glob("*.md")):
        if file.name.startswith("_"):
            continue
        meta, body = kb_loader._parse_front_matter(file.read_text(encoding="utf-8"))
        meta["kb_folders"] = [f.strip() for f in meta.get("kb_folders", "").split(",") if f.strip()]
        meta["needs_blog"] = meta.get("needs_blog", "").lower() == "true"
        prompts[file.stem] = {"meta": meta, "body": body}
    return dict(sorted(prompts.items(), key=lambda kv: int(kv[1]["meta"].get("order", 99))))


@st.cache_resource
def get_store():
    token, repo = secret("GITHUB_TOKEN"), secret("GITHUB_REPO")
    if token and repo:
        try:
            return history.GitHubStore(token, repo, secret("HISTORY_BRANCH", "history"))
        except Exception as exc:  # fall back but tell the user
            st.session_state["store_error"] = str(exc)[:200]
    return history.LocalStore()


@st.cache_data(ttl=60)
def load_history() -> list[dict]:
    return history.load_seed() + get_store().load()


def refresh_history() -> None:
    load_history.clear()


def copy_button(text: str, key: str) -> None:
    """One green button that copies the (edited) draft to the clipboard."""
    import json

    # Escape so draft text can never close the <script> tag.
    payload = json.dumps(text).replace("</", "<\\/").replace("<!--", "<\\!--")
    html = f"""
        <button id="{key}" style="background:#166534;color:#fff;border:0;border-radius:8px;
                padding:8px 18px;font:600 14px sans-serif;cursor:pointer;">📋 Copy text</button>
        <span id="{key}_msg" style="font:13px sans-serif;color:#166534;margin-left:10px;"></span>
        <script>
        const text = {payload};
        const btn = document.getElementById("{key}");
        const msg = document.getElementById("{key}_msg");
        function done(ok) {{ msg.textContent = ok ? "Copied ✓" : "Copy blocked – select the text above and press Ctrl+C"; }}
        btn.onclick = () => {{
          if (navigator.clipboard && window.isSecureContext) {{
            navigator.clipboard.writeText(text).then(() => done(true)).catch(fallback);
          }} else {{ fallback(); }}
        }};
        function fallback() {{
          const ta = document.createElement("textarea");
          ta.value = text; document.body.appendChild(ta); ta.select();
          let ok = false; try {{ ok = document.execCommand("copy"); }} catch (e) {{}}
          document.body.removeChild(ta); done(ok);
        }}
        </script>
        """
    if hasattr(st, "iframe"):          # Streamlit >= 1.5x
        st.iframe(html, height=48)
    else:                              # older Streamlit
        import streamlit.components.v1 as components
        components.html(html, height=48)


# ------------------------------------------------------------------ login
user = auth.login_gate(header)
if not user:
    st.stop()

docs = load_kb_cached()
prompts = load_prompts()
records = load_history()
api_key = secret("GEMINI_API_KEY")
model = secret("GEMINI_MODEL", llm.DEFAULT_MODEL)

with st.sidebar:
    st.markdown(f"### 🌿 {APP_NAME}")
    st.caption(f"Signed in as **{user}**")
    page = st.radio("Go to", ["✍️ Create content", "🗂️ Content history", "📚 Knowledge base", "ℹ️ How to use"],
                    label_visibility="collapsed")
    st.divider()
    st.caption(f"Model: `{model}`" if api_key else "⚠️ Demo mode – no API key set")
    st.caption(f"History saved to: {get_store().name}")
    if st.session_state.get("store_error"):
        st.caption(f"⚠️ GitHub history unavailable: {st.session_state['store_error']}")
    st.caption(f"Knowledge files: {len(docs)} · Past posts: {len(records)}")
    if st.button("Sign out", width="stretch"):
        auth.logout()

header()
st.info("Only public information goes into this tool (website, published blogs, public regulations). "
        "Do not paste customer data, prices, contacts or internal documents.", icon="🔒")


# ------------------------------------------------------------------ pages
def page_create() -> None:
    labels = {key: p["meta"].get("label", key) for key, p in prompts.items()}
    col_a, col_b = st.columns([1.3, 1])
    with col_a:
        ptype = st.selectbox("What do you want to create?", list(labels), format_func=labels.get)
    spec = prompts[ptype]
    meta = spec["meta"]
    product = meta.get("product", "")
    with col_b:
        tone = st.selectbox("Tone", TONES)

    candidate_docs = kb_loader.docs_for_folders(docs, meta["kb_folders"])
    last_used = history.source_last_used(records)

    blog_doc = None
    if meta["needs_blog"]:
        blog_docs = [d for d in docs if d.doc_type == "blog"]
        catalog = next((d for d in docs if d.doc_type == "blog_catalog"), None)
        options = [d.path for d in blog_docs] + (["__catalog__"] if catalog else [])

        def blog_label(path: str) -> str:
            if path == "__catalog__":
                return "Another blog (pick from the catalog – type its title in the topic box)"
            d = next(x for x in blog_docs if x.path == path)
            used = last_used.get(path)
            return f"{d.title}  ·  {d.meta.get('published', '')}" + (f"  ·  last promoted {used}" if used else "")

        choice = st.selectbox("Which blog?", options, format_func=blog_label)
        blog_doc = catalog if choice == "__catalog__" else next(d for d in blog_docs if d.path == choice)

    topic = st.text_input(
        "Topic or angle (optional)",
        placeholder="e.g. 2027 Oregon fee schedule is out – update your EPR budget",
    )
    notes = st.text_area(
        "Extra notes / facts to include (optional)",
        placeholder="Paste a public news link or summary, an event, a deadline… Only public information.",
        height=90,
    )

    with st.expander("Knowledge files used for this draft", expanded=False):
        def doc_label(d: kb_loader.KBDoc) -> str:
            used = last_used.get(d.path)
            return f"{d.path}" + (f"  (last used {used})" if used else "")

        default = [d.path for d in candidate_docs]
        chosen_paths = st.multiselect(
            "Files", [d.path for d in docs if d.path != kb_loader.GUIDELINES_FILE],
            default=default, format_func=lambda p: doc_label(next(d for d in docs if d.path == p)),
        )
        st.caption("guidelines.md is always included.")

    n_variants = st.slider("Number of drafts", 1, 3, 2)

    if st.button("✨ Generate drafts", type="primary", width="stretch"):
        selected = [d for d in docs if d.path in chosen_paths]
        if blog_doc and blog_doc not in selected:
            selected.insert(0, blog_doc)
        system_prompt = (PROMPTS_DIR / "_system.md").read_text(encoding="utf-8").replace(
            "{{GUIDELINES}}", kb_loader.get_guidelines(docs))
        user_prompt = (
            spec["body"]
            .replace("{{N}}", str(n_variants))
            .replace("{{TONE}}", tone)
            .replace("{{TOPIC}}", topic.strip() or "(choose the most useful, timely angle from the knowledge)")
            .replace("{{NOTES}}", notes.strip() or "(none)")
            .replace("{{BLOG}}", blog_doc.as_context() if blog_doc else "")
            .replace("{{KB}}", kb_loader.build_context(selected))
            .replace("{{RECENT}}", history.recent_summary(records, product))
        )
        # Timing: a "cycle" starts at the first Generate click and ends at "Mark as used".
        # Regenerations inside the cycle are counted, so the total time is honest.
        cycle = st.session_state.get("cycle") or {"started": time.time(), "generations": 0, "ai_seconds": 0.0}
        t0 = time.time()
        with st.spinner("Writing drafts…"):
            try:
                variants = llm.generate_variants(system_prompt, user_prompt, api_key, model)
            except llm.LLMError as exc:
                st.error(str(exc))
                return
        ai_seconds = time.time() - t0
        cycle["generations"] += 1
        cycle["ai_seconds"] += ai_seconds
        st.session_state["cycle"] = cycle
        st.session_state["drafts"] = {
            "variants": variants, "ptype": ptype, "label": labels[ptype], "product": product,
            "topic": topic or (blog_doc.title if blog_doc else ""),
            "sources": [d.path for d in selected], "ai_seconds": round(ai_seconds, 1),
        }
        st.session_state.pop("saved_ids", None)

    drafts = st.session_state.get("drafts")
    if not drafts:
        return

    st.markdown("---")
    st.subheader("Drafts – review, edit, copy")
    st.caption(f"Written by AI in {drafts['ai_seconds']} s. Check every fact before posting. "
               "Replace any [ADD SOURCE] / [ADD LINK] placeholders.")
    saved = st.session_state.setdefault("saved_ids", {})
    tabs = st.tabs([f"Draft {i + 1}" for i in range(len(drafts["variants"]))])
    for i, (tab, v) in enumerate(zip(tabs, drafts["variants"])):
        with tab:
            if v.get("angle"):
                st.markdown(f"<span class='pill'>Angle: {v['angle']}</span>", unsafe_allow_html=True)
            similar = history.find_similar(v["text"], records)
            if similar:
                r = similar["record"]
                st.markdown(
                    f"<div class='warn-box'>⚠️ <b>Possible repeat</b> ({similar['reason']}, score {similar['score']:.2f}) "
                    f"of a post from <b>{r.get('date', '')}</b>: “{r.get('text', '').split(chr(10))[0][:140]}”</div>",
                    unsafe_allow_html=True,
                )
                with st.expander("See the earlier post"):
                    st.text(r.get("text", ""))
            edited = st.text_area("Edit", v["text"], height=360, key=f"edit_{i}", label_visibility="collapsed")
            placeholders = edited.count("[ADD")
            st.caption(f"{len(edited)} characters · {len(edited.split())} words"
                       + (f" · ⚠️ {placeholders} placeholder(s) to fill" if placeholders else ""))
            copy_button(edited, key=f"copy_{i}")
            if saved.get(i):
                st.success("Marked as used ✓ – future drafts will avoid repeating it.")
            elif st.button("✅ Mark as used (I posted / will post this)", key=f"save_{i}"):
                cycle = st.session_state.get("cycle") or {"started": time.time(), "generations": 1,
                                                           "ai_seconds": drafts["ai_seconds"]}
                total_seconds = time.time() - cycle["started"]
                timing = {
                    "ai_seconds": round(cycle["ai_seconds"], 1),                    # model writing time
                    "total_minutes": round(total_seconds / 60, 1),                  # first Generate → Mark as used
                    "human_minutes": round(max(total_seconds - cycle["ai_seconds"], 0) / 60, 1),  # review + edit
                    "generations": cycle["generations"],                            # how many times Generate was clicked
                    "edit_percent": round(100 * (1 - SequenceMatcher(None, v["text"], edited).ratio())),
                }
                record = history.new_record(
                    user=user, content_type=drafts["label"], product=drafts["product"],
                    topic=drafts["topic"], sources=drafts["sources"], text=edited, angle=v.get("angle", ""),
                    timing=timing,
                )
                try:
                    get_store().add(record)
                    saved[i] = record["id"]
                    st.session_state.pop("cycle", None)
                    refresh_history()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not save: {exc}")


def page_history() -> None:
    st.subheader("Content history")
    st.caption("Everything marked as used, plus posts published before the app existed. Drafts avoid repeating these.")
    if not records:
        st.write("Nothing yet.")
        return
    products = sorted({r.get("product", "") for r in records})
    col1, col2 = st.columns(2)
    pick_product = col1.multiselect("Product", products, default=products)
    query = col2.text_input("Search text")
    rows = [r for r in records if r.get("product", "") in pick_product
            and (not query or query.lower() in r.get("text", "").lower())]
    rows.sort(key=lambda r: r.get("timestamp", r.get("date", "")), reverse=True)

    timed = [r["timing"] for r in rows if r.get("timing")]
    if timed:
        st.markdown("**Time saved – measured automatically by the app**")
        m1, m2, m3, m4 = st.columns(4)
        avg = lambda key: sum(t.get(key, 0) for t in timed) / len(timed)
        m1.metric("Posts made with ForzoASK", len(timed))
        m2.metric("Avg time per post", f"{avg('total_minutes'):.1f} min")
        m3.metric("Avg AI writing time", f"{avg('ai_seconds'):.0f} s")
        m4.metric("Avg % edited by person", f"{avg('edit_percent'):.0f}%")
        st.caption("Time per post = first 'Generate' click → 'Mark as used' (includes regenerating, reading and editing). "
                   "Compare it with how long a post took before the app.")

    st.dataframe(
        [{"Date": r.get("date"), "Type": r.get("content_type"), "Product": r.get("product"),
          "Minutes": (r.get("timing") or {}).get("total_minutes"),
          "AI sec": (r.get("timing") or {}).get("ai_seconds"),
          "% edited": (r.get("timing") or {}).get("edit_percent"),
          "Opening line": r.get("text", "").split("\n")[0][:120]} for r in rows],
        width="stretch", hide_index=True,
    )
    import csv, io
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "timestamp", "content_type", "product", "topic", "total_minutes", "human_minutes",
                     "ai_seconds", "generations", "edit_percent", "opening_line"])
    for r in rows:
        t = r.get("timing") or {}
        writer.writerow([r.get("date"), r.get("timestamp", ""), r.get("content_type"), r.get("product"), r.get("topic"),
                         t.get("total_minutes", ""), t.get("human_minutes", ""), t.get("ai_seconds", ""),
                         t.get("generations", ""), t.get("edit_percent", ""), r.get("text", "").split("\n")[0][:150]])
    st.download_button("⬇️ Download history (CSV) for the pilot report", buffer.getvalue(),
                       file_name="forzoask_history.csv", mime="text/csv")

    for r in rows[:30]:
        with st.expander(f"{r.get('date')} · {r.get('content_type')} · {r.get('text', '').split(chr(10))[0][:80]}"):
            st.text(r.get("text", ""))
            if r.get("sources"):
                st.caption("Sources: " + ", ".join(r["sources"]))


def page_kb() -> None:
    st.subheader("Knowledge base")
    st.caption("All .md files in the kb/ folder of the GitHub repo. To add knowledge, create a new .md file "
               "in the right folder and push to GitHub – the app picks it up within 5 minutes.")
    last_used = history.source_last_used(records)
    st.dataframe(
        [{"File": d.path, "Title": d.title, "Type": d.doc_type, "Updated / retrieved":
          d.meta.get("last_verified") or d.meta.get("retrieved") or d.meta.get("updated", ""),
          "Last used": last_used.get(d.path, "—"), "Size (words)": len(d.body.split())} for d in docs],
        width="stretch", hide_index=True,
    )
    pick = st.selectbox("Open a file", [d.path for d in docs])
    doc = next(d for d in docs if d.path == pick)
    with st.container(border=True):
        st.markdown(doc.body)
    if st.button("🔄 Reload knowledge base"):
        load_kb_cached.clear()
        st.rerun()


def page_help() -> None:
    st.subheader("How to use ForzoASK")
    st.markdown(
        """
1. **Pick what to create** – an EPR post, a Carbalyze/PCF post, a blog promotion, a Carboventory post, a blog outline or an outreach note.
2. **Add a topic or notes** (optional) – e.g. a public news item, a deadline, an event. Leave blank and the app picks a timely angle.
3. **Generate** – you get 1–3 drafts, each with a different angle. A yellow box warns if a draft is too close to something we already posted.
4. **Review and edit** – check every fact, fill any `[ADD SOURCE]` / `[ADD LINK]`, adjust the wording.
5. **Copy** with the green *Copy text* button (it copies your edited version) and post on LinkedIn (or wherever it goes).
6. **Mark as used** – this saves it to the history so future drafts don't repeat it.

**Adding knowledge:** add a `.md` file to the right `kb/` folder in GitHub (`carbalyze/`, `epr/`, `carboventory/`, `blogs/`, `company/`). Start the file with a short header (title, type, product, url, retrieved date) – copy any existing file as a template.

**Rules:** only public information goes in. A person always reviews before anything is published.
        """
    )


{"✍️ Create content": page_create, "🗂️ Content history": page_history,
 "📚 Knowledge base": page_kb, "ℹ️ How to use": page_help}[page]()
