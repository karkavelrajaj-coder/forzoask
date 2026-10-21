"""Refresh the knowledge base from our public websites.

Run locally (not on Streamlit Cloud):
    pip install requests beautifulsoup4 markdownify
    python scripts/scrape_site.py              # product pages + newest blogs
    python scripts/scrape_site.py --blogs 30   # more blog posts

What it does
  * Downloads each page in PAGES and saves it as markdown in kb/_scraped/<name>.md
  * Finds blog post links on the Carbalyze blog and saves each post to
    kb/_scraped/blogs/<slug>.md (skips posts already saved)
Then a person reviews the files, moves the useful ones into the right kb/
folder (or merges them into the curated summaries) and commits.

Why a review step: scraped pages contain old marketing claims (see
kb/guidelines.md "Never write"). Curated files keep the knowledge clean.
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "kb" / "_scraped"
HEADERS = {"User-Agent": "ForzoASK-KB-refresh/1.0 (internal; contact info@forzotechlabs.com)"}

PAGES = {
    "carbalyze-home": "https://carbalyze.com/en-us",
    "carbalyze-about": "https://carbalyze.com/en-us/about",
    "carbalyze-pricing": "https://carbalyze.com/en-us/pricing",
    "carboventory-home": "https://carboventory.carbalyze.com/",
    "epr-home": "https://sandbox-epr.carbalyze.com/",
    "forzo-home": "https://forzotechlabs.com/",
}
BLOG_INDEXES = ["https://carbalyze.com/en-us/blog/all", "https://carbalyze.com/en-us/blog"]
BLOG_PREFIX = "/en-us/blog/"


def fetch(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def to_markdown(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    md = markdownify(str(main), heading_style="ATX", strip=["img"])
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return title, md


def save(path: Path, title: str, url: str, body: str, doc_type: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = (f"---\ntitle: {title}\ntype: {doc_type}\nsource: {url}\nurl: {url}\n"
             f"retrieved: {date.today().isoformat()}\nstatus: raw-scrape (review before use)\n---\n\n")
    path.write_text(front + body + "\n", encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")


def blog_links() -> list[str]:
    links: list[str] = []
    for index in BLOG_INDEXES:
        try:
            soup = BeautifulSoup(fetch(index), "html.parser")
        except requests.RequestException as exc:
            print(f"! could not read {index}: {exc}")
            continue
        for a in soup.find_all("a", href=True):
            href = urljoin(index, a["href"])
            path = urlparse(href).path.rstrip("/")
            slug = path[len(BLOG_PREFIX):] if path.startswith(BLOG_PREFIX) else ""
            if slug and "/" not in slug and slug not in ("all",) and href not in links:
                links.append(href.split("?")[0])
    return links


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blogs", type=int, default=10, help="max number of new blog posts to fetch")
    args = parser.parse_args()

    for name, url in PAGES.items():
        try:
            title, md = to_markdown(fetch(url))
            save(OUT / f"{name}.md", title or name, url, md, "page")
        except requests.RequestException as exc:
            print(f"! {url}: {exc}")
        time.sleep(1)

    links = blog_links()
    if not links:
        print("No blog links found in the HTML (the blog list may be rendered by JavaScript). "
              "Save those posts manually or point BLOG_INDEXES at the sitemap.")
    fetched = 0
    for url in links:
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        target = OUT / "blogs" / f"{slug}.md"
        if target.exists() or (ROOT / "kb" / "blogs" / f"{slug}.md").exists():
            continue
        try:
            title, md = to_markdown(fetch(url))
            save(target, title or slug, url, md, "blog")
            fetched += 1
        except requests.RequestException as exc:
            print(f"! {url}: {exc}")
        if fetched >= args.blogs:
            break
        time.sleep(1)
    print(f"Done. {fetched} new blog post(s). Review kb/_scraped/ before committing.")


if __name__ == "__main__":
    main()
