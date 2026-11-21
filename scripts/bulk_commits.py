#!/usr/bin/env python3
"""
Spread N commits across all of your own (non-fork, non-archived) GitHub repos.

Runs from the "bulk-commits" workflow (Actions tab -> Run workflow), or locally:
    python scripts/bulk_commits.py --dry-run      # show the plan only
    python scripts/bulk_commits.py --total 400

Env: GH_TOKEN (PAT with Contents: read & write on your repos; needed in Actions),
     GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL (fall back to the defaults below).

What it does per repo:
  - clones the repo into a temp folder
  - appends one line per commit to .activity/log.md (no other file is touched)
  - commits with your GitHub noreply email so every commit counts on your graph
  - pushes once to the default branch, then deletes the temp clone

Needs: git on PATH, and git already signed in to GitHub as you.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

NAME = os.getenv("GIT_AUTHOR_NAME") or "Tejaswi Ponukupati"
EMAIL = os.getenv("GIT_AUTHOR_EMAIL") or "148254552+tej9911@users.noreply.github.com"
TOKEN = os.getenv("GH_TOKEN", "")


def list_repos(user: str) -> list[dict]:
    repos, page = [], 1
    while True:
        url = f"https://api.github.com/users/{user}/repos?per_page=100&page={page}&type=owner"
        headers = {"Accept": "application/vnd.github+json"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.load(r)
        if not batch:
            break
        repos.extend(batch)
        page += 1
    # forks and archived repos don't count / can't be pushed to
    return [r for r in repos if not r["fork"] and not r["archived"]]


def split(total: int, n: int) -> list[int]:
    base, extra = divmod(total, n)
    return [base + (1 if i < extra else 0) for i in range(n)]


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def commit_to_repo(repo: dict, count: int, workdir: Path) -> None:
    dest = workdir / repo["name"]
    url = repo["clone_url"]
    if TOKEN and url.startswith("https://"):
        url = url.replace("https://", f"https://x-access-token:{TOKEN}@", 1)
    git(workdir, "clone", "--quiet", url, str(dest))

    # empty repo: create the default branch
    has_commits = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest,
                                 capture_output=True).returncode == 0
    branch = repo.get("default_branch") or "main"
    if not has_commits:
        git(dest, "checkout", "-b", branch)

    git(dest, "config", "user.name", NAME)
    git(dest, "config", "user.email", EMAIL)

    log = dest / ".activity" / "log.md"
    log.parent.mkdir(exist_ok=True)
    for i in range(1, count + 1):
        with log.open("a", encoding="utf-8") as f:
            f.write(f"- {dt.datetime.now().isoformat(timespec='seconds')} update {i}\n")
        git(dest, "add", ".activity/log.md")
        git(dest, "commit", "--quiet", "-m", f"chore: activity log update {i}")
    git(dest, "push", "--quiet", "origin", f"HEAD:{branch}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="tej9911")
    ap.add_argument("--total", type=int, default=400)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repos = list_repos(args.user)
    if not repos:
        sys.exit("No eligible repos found (forks and archived repos are skipped).")
    plan = list(zip(repos, split(args.total, len(repos))))

    print(f"{len(repos)} repos, {args.total} commits total:")
    for repo, n in plan:
        print(f"  {repo['name']:<40} {n} commits  (branch: {repo.get('default_branch')})")
    if args.dry_run:
        print("\nDry run - nothing changed.")
        return

    workdir = Path(tempfile.mkdtemp(prefix="bulk_commits_"))
    done = 0
    try:
        for repo, n in plan:
            if n == 0:
                continue
            print(f"-> {repo['name']}: {n} commits ...", end=" ", flush=True)
            try:
                commit_to_repo(repo, n, workdir)
                done += n
                print("pushed")
            except subprocess.CalledProcessError as e:
                err = e.stderr.decode(errors="ignore").strip()
                if TOKEN:
                    err = err.replace(TOKEN, "***")
                print(f"FAILED: {err[:200]}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    print(f"\nDone: {done}/{args.total} commits pushed. "
          "Your profile graph can take a few minutes to update.")


if __name__ == "__main__":
    main()
