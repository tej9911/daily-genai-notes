# daily-genai-notes: GitHub Activity Agent

An agent that runs on GitHub Actions and keeps my contribution graph active. It has two features:

| Feature | Workflow | When it runs | What it does |
|---|---|---|---|
| **Daily streak** | `daily-streak-agent` | Every day at 18:47 and 22:37 IST | Commits only if I haven't contributed that day |
| **Bulk commits** | `bulk-commits` | Manually, from the Actions tab | Spreads N commits (default 400) across all my repos |

---

## 1. Daily streak agent

```
OBSERVE  → today's note exists?  contributions today > 0?
DECIDE   → yes: skip   | no: act
ACT      → write note → notes/YYYY/MM/DD.md → commit (my email) → push
```

- Reads today's contribution count through GitHub's GraphQL API, using the `GH_PAT` secret.
- If `ANTHROPIC_API_KEY` is set, Claude writes a short GenAI study note. Without it, a dated log line is committed.
- The second run is a safety net. It skips if the first run already committed.

## 2. Bulk commits

**Actions → bulk-commits → Run workflow**

| Input | Default | Meaning |
|---|---|---|
| `total` | 400 | Total commits to make |
| `dry_run` | ✅ ticked | Only prints which repo gets how many commits. Untick to actually push. |

- Uses every repo I own that isn't a fork or archived, and splits the total evenly.
- Each commit appends one line to `.activity/log.md` in that repo and is pushed to the default branch. No other files are touched.

---

## Setup

**Settings → Secrets and variables → Actions**

| Type | Name | Value |
|---|---|---|
| Variable | `GIT_AUTHOR_NAME` | My name |
| Variable | `GIT_AUTHOR_EMAIL` | My GitHub noreply email (commits only count with an email linked to my account) |
| Secret | `GH_PAT` | Fine-grained token. Read-only for the daily agent. **Contents: Read and write on all repositories** for bulk commits. |
| Secret | `ANTHROPIC_API_KEY` | Optional, for Claude-written notes |

**Settings → Actions → General → Workflow permissions → Read and write.**

## Project structure

```
.github/workflows/
  streak.yml        # daily scheduled agent
  bulk.yml          # manual bulk-commit workflow
scripts/
  streak_agent.py   # observe → decide → act logic
  bulk_commits.py   # repo discovery + commit distribution
notes/              # daily notes written by the agent
```

## Run locally

```bash
DRY_RUN=1 python scripts/streak_agent.py
python scripts/bulk_commits.py --dry-run --total 400
```

## Gotchas
- Commits count only on a repo's **default branch** and in repos that aren't forks.
- GitHub can delay scheduled runs, so the cron minutes avoid `:00`.
- Fine-grained tokens expire. Renew `GH_PAT` before it does.
