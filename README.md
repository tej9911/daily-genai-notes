# GitHub Streak Agent

A scheduled agent that keeps your GitHub contribution streak alive **only on days you didn't already commit**. When it does step in, it writes a short Claude-generated GenAI study note, so the repo turns into a real daily-notes collection instead of a junk log.

```
GitHub Actions cron (18:47 IST, 22:37 IST)
        │
        ▼
OBSERVE  → today's note exists?  contributions today > 0?
DECIDE   → yes: skip   | no: act
ACT      → Claude writes note → notes/YYYY/MM/DD.md → commit (your email) → push
```

## Setup (about 10 minutes)

1. **Create a new public repo** on GitHub (e.g. `daily-genai-notes`) and push these files to it.
2. **Repo → Settings → Secrets and variables → Actions**
   - **Variables** tab:
     - `GIT_AUTHOR_NAME` = your name
     - `GIT_AUTHOR_EMAIL` = an email **verified on your GitHub account**, or your
       `<id>+<username>@users.noreply.github.com` address (Settings → Emails).
       ⚠️ If this email isn't linked to your account, the commits **won't count**.
   - **Secrets** tab:
     - `ANTHROPIC_API_KEY`: optional. Without it the agent commits a plain log line.
     - `GH_PAT`: optional. A fine-grained token with **no extra permissions**
       (public read is enough). It lets the agent see whether you already committed today.
       Without it, the agent commits every day.
3. **Settings → Actions → General → Workflow permissions** → choose *Read and write*.
4. **Actions tab → daily-streak-agent → Run workflow** to test it once.

## Test locally

```bash
pip install anthropic
DRY_RUN=1 python scripts/streak_agent.py                 # fallback note, no commit
DRY_RUN=1 ANTHROPIC_API_KEY=sk-... python scripts/streak_agent.py
```

## Gotchas
- Commits count only on the repo's **default branch** and in a repo that isn't a fork.
- GitHub may delay scheduled runs at busy times. That's why there are two runs and the cron minutes avoid `:00`.
- In public repos, GitHub disables scheduled workflows after 60 days without repo activity. This repo's daily commits count as activity, but if the workflow ever stops, re-enable it from the Actions tab.
