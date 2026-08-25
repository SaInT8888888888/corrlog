#!/usr/bin/env python3
"""corrlog adoption tracker — checks GitHub signals weekly and reports.

Read-only: hits the public GitHub REST API (no token needed for public repos,
rate-limited to 60/hr which is plenty for one check). Reports stars, forks,
open issues, and (via the search API) how many times 'corrlog' appears in
public code/docs. Writes a JSON snapshot so week-over-week deltas are visible.

Run: python3 scripts/track_adoption.py  (from the corrlog-sdk repo root)
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone

REPO = "SaInT8888888888/corrlog"
SNAPSHOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        ".adoption.json")


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "corrlog-adoption-tracker", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _search_mentions() -> int:
    """Count of public issue/PR results referencing our repo explicitly.

    Searches for the full 'SaInT8888888888/corrlog' path so generic substrings
    (e.g. 'Corrfunc') don't count as adoption.
    """
    q = urllib.parse.quote("SaInT8888888888/corrlog")
    try:
        d = _get(f"https://api.github.com/search/issues?q={q}&per_page=1")
        return d.get("total_count", 0)
    except Exception:
        return -1  # rate-limited or transient; don't crash the run


def main() -> None:
    repo = _get(f"https://api.github.com/repos/{REPO}")
    now = datetime.now(timezone.utc).isoformat()

    prev = {}
    if os.path.exists(SNAPSHOT):
        try:
            prev = json.load(open(SNAPSHOT))
        except Exception:
            prev = {}

    snap = {
        "checked_at": now,
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "watchers": repo.get("subscribers_count", 0),
        "mentions_issues": _search_mentions(),
    }
    json.dump(snap, open(SNAPSHOT, "w"), indent=2)

    print(f"corrlog adoption @ {now}")
    print(f"  stars:        {snap['stars']}  (+{snap['stars'] - prev.get('stars', snap['stars'])})")
    print(f"  forks:        {snap['forks']}  (+{snap['forks'] - prev.get('forks', snap['forks'])})")
    print(f"  open issues:  {snap['open_issues']}")
    print(f"  watchers:     {snap['watchers']}")
    print(f"  'corrlog' mentions (issues+PRs): {snap['mentions_issues']}")
    if snap["stars"] > 0 or snap["forks"] > 0 or snap["mentions_issues"] > 0:
        print("\n  >> real adoption signal — check what they're doing with it")
    else:
        print("\n  >> zero yet — expected this early; the launch post drives the first signal")


if __name__ == "__main__":
    main()
