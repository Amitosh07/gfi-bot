#!/usr/bin/env python3
"""
Checks a list of GitHub repos for newly-created beginner-friendly issues and
posts any new ones to a Discord channel via webhook.

State (which issues have already been seen) is stored in state.json in this
same folder. The GitHub Actions workflow commits that file back to the repo
after every run, so the bot never re-announces the same issue twice.
"""

import json
import http.client
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

# ---- Configuration ---------------------------------------------------

REPOS = [
    "zulip/zulip",
    "pytorch/pytorch",
    "keras-team/keras",
    "ollama/ollama",
    "vllm-project/vllm",
    "huggingface/transformers",
    "scikit-learn/scikit-learn",
    "opencv/opencv",
]

# Default label to watch for. Some repos don't use "good first issue"
# exactly, or currently have zero open ones under it â€” add fallback labels
# per repo here so the bot still catches their beginner-tagged issues.
DEFAULT_LABELS = ["good first issue"]
REPO_LABELS = {
    "huggingface/transformers": ["good first issue", "Good Difficulty Issue", "help wanted"],
    "scikit-learn/scikit-learn": ["good first issue", "help wanted", "Moderate"],
    "opencv/opencv": ["good first issue", "help wanted"],
}

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

# Discord can only @mention a user by their numeric ID, not their @username.
# Leave DISCORD_USER_ID blank to skip the mention and just post plainly.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_USER_ID = os.environ.get("DISCORD_USER_ID", "")  # optional, numeric

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # optional, raises rate limit

# ---- GitHub -----------------------------------------------------------

def gh_headers():
    headers = {
        "User-Agent": "gfi-bot",
        "Accept": "application/vnd.github+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def fetch_open_issues(repo, retries=2):
    labels = REPO_LABELS.get(repo, DEFAULT_LABELS)
    label_clause = " OR ".join(f'label:"{l}"' for l in labels)
    q = f'repo:{repo} state:open ({label_clause})'
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode({
        "q": q,
        "sort": "created",
        "order": "desc",
        "per_page": 25,
    })
    req = urllib.request.Request(url, headers=gh_headers())
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req) as r:
                data = json.load(r)
            return data.get("items", [])
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < retries:
                wait = 10 * (attempt + 1)
                print(f"Rate limited on {repo}, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


# ---- Discord ------------------------------------------------------------

def post_to_discord(repo, issue):
    if not DISCORD_WEBHOOK_URL:
        print(
            f"Discord webhook is not configured; not marking "
            f"{repo}#{issue['number']} as seen.",
            file=sys.stderr,
        )
        return False

    mention = f"<@{DISCORD_USER_ID}> " if DISCORD_USER_ID else ""
    matched_labels = ", ".join(
        l["name"] for l in issue.get("labels", [])
        if l["name"].lower() in {x.lower() for x in REPO_LABELS.get(repo, DEFAULT_LABELS)}
    )
    content = (
        f"{mention}ðŸ†• **New beginner-friendly issue** in `{repo}`"
        + (f" [{matched_labels}]" if matched_labels else "")
        + f"\n**{issue['title']}**\n{issue['html_url']}"
    )
    payload = json.dumps({"content": content}).encode("utf-8")
    webhook = urllib.parse.urlsplit(DISCORD_WEBHOOK_URL)
    if webhook.scheme != "https" or not webhook.netloc:
        print(
            f"Discord webhook configuration is invalid; not marking "
            f"{repo}#{issue['number']} as seen.",
            file=sys.stderr,
        )
        return False

    request_path = webhook.path or "/"
    if webhook.query:
        request_path += f"?{webhook.query}"

    connection = None
    try:
        connection = http.client.HTTPSConnection(webhook.netloc, timeout=15)
        connection.request(
            "POST",
            request_path,
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        status = response.status
        response.read()
        if not 200 <= status < 300:
            print(
                f"Discord rejected {repo}#{issue['number']} (HTTP {status}); "
                "not marking it as seen.",
                file=sys.stderr,
            )
            return False
        print(f"Posted: {repo}#{issue['number']}")
        return True
    except http.client.HTTPException:
        print(
            f"Discord post failed for {repo}#{issue['number']}; "
            "not marking it as seen.",
            file=sys.stderr,
        )
        return False
    except OSError:
        print(
            f"Discord post failed for {repo}#{issue['number']} due to a network error; "
            "not marking it as seen.",
            file=sys.stderr,
        )
        return False
    except Exception:
        print(
            f"Discord post failed unexpectedly for {repo}#{issue['number']}; "
            "not marking it as seen.",
            file=sys.stderr,
        )
        return False
    finally:
        if connection is not None:
            connection.close()
        time.sleep(1)  # be gentle with Discord's rate limit


# ---- State --------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


# ---- Main -----------------------------------------------------------------

def main():
    state = load_state()
    any_new = False

    for repo in REPOS:
        seen = set(state.get(repo, []))
        try:
            issues = fetch_open_issues(repo)
        except Exception as e:
            print(f"ERROR fetching {repo}: {e}", file=sys.stderr)
            time.sleep(3)
            continue

        new_issues = [it for it in issues if it["number"] not in seen]
        if new_issues:
            any_new = True

        successfully_seen = [
            issue["number"] for issue in issues if issue["number"] in seen
        ]
        # Post oldest-first so Discord message order reads naturally
        for issue in reversed(new_issues):
            if post_to_discord(repo, issue):
                successfully_seen.append(issue["number"])

        # Keep only matching issues that were already seen or whose Discord
        # notification succeeded. Closed/relabeled issues drop out over time.
        state[repo] = successfully_seen
        time.sleep(3)  # stay under GitHub's search rate limit

    save_state(state)

    if not any_new:
        print("No new issues found this run.")


if __name__ == "__main__":
    main()
