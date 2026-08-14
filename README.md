# good-first-issue Discord bot

Polls these 8 repos every 30 minutes for newly opened beginner-friendly
issues and posts any new ones to a Discord channel:

`zulip/zulip`, `pytorch/pytorch`, `keras-team/keras`, `ollama/ollama`,
`vllm-project/vllm`, `huggingface/transformers`, `scikit-learn/scikit-learn`,
`opencv/opencv`

Most repos are watched under the `good first issue` label. A few
(`huggingface/transformers`, `scikit-learn/scikit-learn`, `opencv/opencv`)
currently have **zero** open issues under that exact label, so the script
also checks their other beginner-labels (`help wanted`, `Good Difficulty
Issue`, `Moderate`) — see `REPO_LABELS` at the top of `check_new_issues.py`
if you want to tune this further.

## ⚠️ About the webhook URL

A Discord webhook URL is a bearer credential — anyone who has it can post to
your channel. **Do not commit it into any file in this repo.** It only ever
goes into GitHub's encrypted repo secret (step 2 below), never into code.
If you've shared it anywhere public, regenerate it from Discord's webhook
settings first.

## 1. Add your secrets

Push these files to a new (can be private) GitHub repo, then go to:
**Settings → Secrets and variables → Actions → New repository secret**

| Secret name           | Value                                                      |
|------------------------|-------------------------------------------------------------|
| `DISCORD_WEBHOOK_URL`  | your webhook URL from Discord (Channel Settings → Integrations → Webhooks) |
| `DISCORD_USER_ID`      | (optional) your numeric Discord user ID, for @mentions      |

Discord can't @mention someone by `@username` — only by numeric ID. To get
yours: Discord → User Settings → Advanced → enable **Developer Mode**, then
right-click your name → **Copy User ID**. Leave this secret out if you just
want plain posts, no ping.

You do **not** need to set `GITHUB_TOKEN` yourself — GitHub Actions injects
one automatically, which raises the API rate limit and lets the workflow
commit `state.json` back.

## 2. Turn it on

- Go to the **Actions** tab of the repo → enable workflows if prompted.
- It then runs automatically every 30 minutes.
- To test immediately: Actions tab → "Check for new good-first-issues" →
  **Run workflow**.

## Notes

- **First run posts every currently-open issue** in all 8 repos (nothing has
  been "seen" yet) — expect a burst of messages. After that, only genuinely
  new issues get posted.
- To add/remove repos, edit the `REPOS` list in `check_new_issues.py`.
- To change frequency, edit the `cron` line in the workflow file
  (`*/30 * * * *` = every 30 min; GitHub's scheduler can drift a few minutes
  under load — normal).
- The script retries once with backoff on GitHub rate-limit errors (403/429).

