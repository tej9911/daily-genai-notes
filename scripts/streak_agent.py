#!/usr/bin/env python3
"""
GitHub Streak Agent
===================
A small agent that runs on a schedule (GitHub Actions) and follows an
OBSERVE -> DECIDE -> ACT loop:

  1. OBSERVE  - Did I already contribute today (in my timezone)?
                (checks GitHub's GraphQL contribution data + local notes)
  2. DECIDE   - If yes, do nothing (your real work already kept the streak).
                If no, the agent steps in.
  3. ACT      - Ask Claude for a short, example-driven GenAI note on a
                topic not covered before, save it to notes/YYYY/MM/DD.md,
                commit it with YOUR email (so it counts on your graph), push.

Environment variables (set in the workflow):
  GH_USER            GitHub username (defaults to repo owner in the workflow)
  GH_TOKEN           PAT used only to READ your contribution calendar (optional)
  ANTHROPIC_API_KEY  Optional. Without it, a plain log entry is committed.
  GIT_AUTHOR_NAME    Your name for the commit
  GIT_AUTHOR_EMAIL   An email verified on your GitHub account (or your
                     <id>+<user>@users.noreply.github.com address)
  STREAK_TZ          Timezone for "today" (default Asia/Kolkata)
  CLAUDE_MODEL       Default claude-haiku-5-5 (cheap; ~fractions of a cent/day)
  DRY_RUN            "1" = do everything except commit/push
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("STREAK_TZ", "Asia/Kolkata"))
REPO_ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = REPO_ROOT / "notes"
TOPICS_FILE = REPO_ROOT / "topics_covered.txt"
MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
DRY_RUN = os.getenv("DRY_RUN") == "1"


def log(msg: str) -> None:
    print(f"[streak-agent] {msg}", flush=True)


# ----------------------------------------------------------------- OBSERVE
def contributions_today(user: str, token: str) -> int | None:
    """Return today's contribution count, or None if it can't be determined."""
    if not (user and token):
        return None
    now = dt.datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
        }
      }
    }"""
    body = json.dumps({
        "query": query,
        "variables": {"login": user, "from": start.isoformat(), "to": now.isoformat()},
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except Exception as e:  # network/auth issues shouldn't break the streak
        log(f"could not read contribution calendar ({e}); will act to be safe")
        return None


def today_note_path() -> Path:
    d = dt.datetime.now(TZ).date()
    return NOTES_DIR / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.md"


# ----------------------------------------------------------------- ACT: generate
def covered_topics() -> list[str]:
    if TOPICS_FILE.exists():
        return [t.strip() for t in TOPICS_FILE.read_text().splitlines() if t.strip()]
    return []


def generate_note(done: list[str]) -> tuple[str, str]:
    """Return (topic, markdown). Uses Claude if a key is present, else a fallback."""
    today = dt.datetime.now(TZ).date().isoformat()
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "daily-log", f"# {today}\n\nDaily log entry.\n"

    import anthropic  # imported lazily so DRY_RUN without the SDK still works

    recent = ", ".join(done[-60:]) or "none yet"
    prompt = (
        "Write a short daily study note (150-250 words) on ONE Generative AI / "
        "agentic AI / LLM engineering concept for a CS student who already builds agents. "
        "Pick a concept NOT in this list: " + recent + ".\n"
        "Include: a 2-line explanation, one concrete example (code snippet or worked "
        "scenario), and one common pitfall.\n"
        "Output format, exactly:\nTOPIC: <short topic name>\n---\n<markdown note starting with a # heading>"
    )
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()

    topic, _, body = text.partition("---")
    topic = topic.replace("TOPIC:", "").strip() or "untitled"
    body = body.strip() or text
    return topic, f"<!-- {today} -->\n{body}\n"


# ----------------------------------------------------------------- ACT: commit
def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=REPO_ROOT, check=True)


def commit_and_push(note: Path, topic: str) -> None:
    name = os.getenv("GIT_AUTHOR_NAME")
    email = os.getenv("GIT_AUTHOR_EMAIL")
    if not (name and email):
        sys.exit("GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL not set - the commit would not count on your graph.")
    git("config", "user.name", name)
    git("config", "user.email", email)
    git("add", str(note.relative_to(REPO_ROOT)), str(TOPICS_FILE.relative_to(REPO_ROOT)))
    git("commit", "-m", f"notes: {topic} ({dt.datetime.now(TZ).date()})")
    git("push")


# ----------------------------------------------------------------- MAIN LOOP
def main() -> None:
    note = today_note_path()

    # OBSERVE
    if note.exists():
        log(f"{note.relative_to(REPO_ROOT)} already exists - nothing to do.")
        return
    count = contributions_today(os.getenv("GH_USER", ""), os.getenv("GH_TOKEN", ""))
    log(f"contributions so far today: {count if count is not None else 'unknown'}")

    # DECIDE
    if count and count > 0:
        log("you already contributed today - streak is safe, skipping.")
        return

    # ACT
    done = covered_topics()
    topic, md = generate_note(done)
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(md)
    TOPICS_FILE.write_text("\n".join(done + [topic]) + "\n")
    log(f"wrote note on '{topic}' -> {note.relative_to(REPO_ROOT)}")

    if DRY_RUN:
        log("DRY_RUN=1, not committing.")
        return
    commit_and_push(note, topic)
    log("pushed. streak maintained.")


if __name__ == "__main__":
    main()
