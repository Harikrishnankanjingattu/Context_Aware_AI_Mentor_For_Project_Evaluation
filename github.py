#!/usr/bin/env python3
"""
github_commits.py

Run it, paste a GitHub repo link when asked, and it prints every commit
in that repo (handles pagination automatically).
"""

import re
import sys
import time
from urllib.parse import urlparse

import requests

GITHUB_API = "https://api.github.com"


def parse_repo_url(url: str):
    url = url.strip()
    parsed = urlparse(url if "://" in url else f"https://{url}")
    parts = [p for p in parsed.path.split("/") if p]
    if "github.com" not in parsed.netloc or len(parts) < 2:
        raise ValueError("That doesn't look like a valid GitHub repo URL.")
    owner, repo = parts[0], parts[1]
    return owner, repo.removesuffix(".git")

def fetch_commits(url: str) -> list:
    """Fetch commits from a GitHub repo URL. Returns a list of dictionaries with commit info."""
    owner, repo = parse_repo_url(url)
    api_url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    params = {"per_page": 100}
    commits_data = []

    while api_url:
        resp = requests.get(api_url, params=params, timeout=30)
        
        if resp.status_code == 404:
            raise ValueError(f"Repo '{owner}/{repo}' not found (or it's private).")
        if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
            raise PermissionError("GitHub API rate limit exceeded.")
        
        resp.raise_for_status()

        for commit in resp.json():
            sha = commit["sha"][:7]
            info = commit.get("commit", {})
            author = (info.get("author") or {}).get("name", "Unknown")
            date = (info.get("author") or {}).get("date", "Unknown")
            message = info.get("message", "").split("\n")[0]
            commits_data.append({
                "sha": sha,
                "author": author,
                "date": date,
                "message": message
            })

        api_url = resp.links.get("next", {}).get("url")
        params = None  # already included in the "next" URL

    return commits_data

def main():
    url = input("Enter a GitHub repo URL: ").strip()

    try:
        commits = fetch_commits(url)
        print(f"\nFetching commits...\n")
        for count, c in enumerate(commits, 1):
            print(f"{count:>4}. [{c['sha']}] {c['date']}  {c['author']}: {c['message']}")
        print(f"\nTotal commits: {len(commits)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()