"""Content history: what has already been used, and repetition checks.

Storage:
  * GitHubStore – saves data/history.json on a separate branch ("history") of the
    app's own repo, so it survives restarts on Streamlit Cloud and does NOT
    trigger a redeploy of the main branch.
  * LocalStore  – a local JSON file, used when no GitHub token is configured
    (local testing). On Streamlit Cloud this resets on every restart.

data/history_seed.json (in the main branch) holds posts published before the
app existed, so repetition checks work from day one.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).parent
SEED_FILE = ROOT / "data" / "history_seed.json"
LOCAL_FILE = ROOT / "data" / "history_local.json"
HISTORY_PATH_IN_REPO = "data/history.json"

SIMILARITY_WARN = 0.35   # TF-IDF cosine similarity that triggers a warning
HOOK_WARN = 0.60         # first-line similarity that triggers a warning


def new_record(user: str, content_type: str, product: str, topic: str,
               sources: list[str], text: str, angle: str = "", timing: dict | None = None) -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": user,
        "content_type": content_type,
        "product": product,
        "topic": topic.strip()[:200],
        "angle": angle,
        "sources": sources,
        "text": text.strip(),
        "timing": timing or {},
    }


def load_seed() -> list[dict]:
    if SEED_FILE.exists():
        return json.loads(SEED_FILE.read_text(encoding="utf-8"))
    return []


class LocalStore:
    name = "local file (resets when the app restarts)"

    def __init__(self, path: Path = LOCAL_FILE):
        self.path = path

    def load(self) -> list[dict]:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return []

    def add(self, record: dict) -> None:
        records = self.load()
        records.append(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


class GitHubStore:
    name = "GitHub (history branch)"

    def __init__(self, token: str, repo_name: str, branch: str = "history"):
        from github import Auth, Github

        self.repo = Github(auth=Auth.Token(token)).get_repo(repo_name)
        self.branch = branch
        self._ensure_branch()

    def _ensure_branch(self) -> None:
        from github import GithubException

        try:
            self.repo.get_branch(self.branch)
        except GithubException:
            base = self.repo.get_branch(self.repo.default_branch)
            self.repo.create_git_ref(ref=f"refs/heads/{self.branch}", sha=base.commit.sha)

    def _get_file(self):
        from github import GithubException

        try:
            return self.repo.get_contents(HISTORY_PATH_IN_REPO, ref=self.branch)
        except GithubException as exc:
            if exc.status == 404:
                return None
            raise

    def load(self) -> list[dict]:
        file = self._get_file()
        if file is None:
            return []
        return json.loads(file.decoded_content.decode("utf-8"))

    def add(self, record: dict) -> None:
        from github import GithubException

        for _ in range(3):  # retry if two people save at the same moment
            file = self._get_file()
            records = json.loads(file.decoded_content.decode("utf-8")) if file else []
            records.append(record)
            payload = json.dumps(records, ensure_ascii=False, indent=2)
            message = f"history: {record['content_type']} by {record['user']}"
            try:
                if file:
                    self.repo.update_file(HISTORY_PATH_IN_REPO, message, payload, file.sha, branch=self.branch)
                else:
                    self.repo.create_file(HISTORY_PATH_IN_REPO, message, payload, branch=self.branch)
                return
            except GithubException as exc:
                if exc.status in (409, 422):
                    continue
                raise
        raise RuntimeError("Could not save to GitHub after 3 attempts. Please try again.")


# ---------------------------------------------------------------- repetition

def recent_summary(records: list[dict], product: str | None = None, limit: int = 20) -> str:
    """Short list of recent posts for the prompt, so the model avoids them."""
    items = sorted(records, key=lambda r: r.get("date", ""), reverse=True)
    if product:
        same = [r for r in items if r.get("product") == product]
        other = [r for r in items if r.get("product") != product]
        items = same + other
    lines = []
    for r in items[:limit]:
        first_line = r.get("text", "").strip().split("\n")[0][:160]
        lines.append(f"- {r.get('date', '')} | {r.get('content_type', '')} | {r.get('product', '')} | "
                     f"topic: {r.get('topic', '')[:100]} | opening line: {first_line}")
    return "\n".join(lines) if lines else "(no content published yet)"


def _first_line(text: str) -> str:
    return text.strip().split("\n")[0].strip().lower()


def find_similar(draft: str, records: list[dict]) -> dict | None:
    """Return the most similar past record if above the warning thresholds."""
    texts = [r.get("text", "") for r in records if r.get("text")]
    if not texts or not draft.strip():
        return None
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform(texts + [draft])
    scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()

    best_i = int(scores.argmax())
    best_score = float(scores[best_i])
    hook_scores = [SequenceMatcher(None, _first_line(draft), _first_line(t)).ratio() for t in texts]
    best_hook_i = max(range(len(hook_scores)), key=hook_scores.__getitem__)
    best_hook = hook_scores[best_hook_i]

    valid = [r for r in records if r.get("text")]
    if best_score >= SIMILARITY_WARN:
        return {"record": valid[best_i], "score": best_score, "reason": "similar content"}
    if best_hook >= HOOK_WARN:
        return {"record": valid[best_hook_i], "score": best_hook, "reason": "similar opening line"}
    return None


def source_last_used(records: list[dict]) -> dict[str, str]:
    """Map kb file path -> last date it was used as a source."""
    last: dict[str, str] = {}
    for r in records:
        for s in r.get("sources", []):
            if r.get("date", "") > last.get(s, ""):
                last[s] = r["date"]
    return last
