"""Load the markdown knowledge base (kb/) and build prompt context.

Every .md file under kb/ is one knowledge document. An optional front-matter
block (--- key: value ---) at the top gives it a title, type, product, url, etc.
To add knowledge: create a new .md file in the right kb/ sub-folder and push it
to GitHub. Nothing else needs to change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

KB_DIR = Path(__file__).parent / "kb"
GUIDELINES_FILE = "guidelines.md"


@dataclass
class KBDoc:
    path: str                      # relative to kb/, e.g. "epr/product-overview.md"
    meta: dict = field(default_factory=dict)
    body: str = ""

    @property
    def title(self) -> str:
        return self.meta.get("title") or Path(self.path).stem.replace("-", " ").title()

    @property
    def folder(self) -> str:
        parts = Path(self.path).parts
        return parts[0] if len(parts) > 1 else ""

    @property
    def doc_type(self) -> str:
        return self.meta.get("type", "")

    def as_context(self) -> str:
        header = f"### SOURCE: {self.path} — {self.title}"
        extras = [f"{k}: {self.meta[k]}" for k in ("url", "published", "last_verified", "retrieved") if k in self.meta]
        if extras:
            header += "\n(" + "; ".join(extras) + ")"
        return f"{header}\n{self.body.strip()}\n"


def _parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip()
    return meta, text[end + 4:].lstrip("\n")


def load_kb(kb_dir: Path = KB_DIR) -> list[KBDoc]:
    docs = []
    for file in sorted(kb_dir.rglob("*.md")):
        rel = file.relative_to(kb_dir)
        if any(part.startswith("_") for part in rel.parts[:-1]):
            continue  # folders like kb/_scraped/ hold raw, unreviewed pages
        text = file.read_text(encoding="utf-8")
        meta, body = _parse_front_matter(text)
        docs.append(KBDoc(path=file.relative_to(kb_dir).as_posix(), meta=meta, body=body))
    return docs


def get_guidelines(docs: list[KBDoc]) -> str:
    for d in docs:
        if d.path == GUIDELINES_FILE:
            return d.body
    return ""


def docs_for_folders(docs: list[KBDoc], folders: list[str]) -> list[KBDoc]:
    """All docs in the given top-level kb/ folders (guidelines excluded)."""
    return [d for d in docs if d.folder in folders and d.path != GUIDELINES_FILE]


def build_context(selected: list[KBDoc], max_chars: int = 120_000) -> str:
    """Concatenate selected docs, trimming if the total grows too large."""
    parts, total = [], 0
    for d in selected:
        chunk = d.as_context()
        if total + len(chunk) > max_chars:
            parts.append(f"### SOURCE: {d.path} — (skipped: context limit reached)\n")
            continue
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts)
