from __future__ import annotations
import logging
from typing import List
import requests

from .config import GITHUB_ACCESS_TOKEN

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


def fetch_pull_request_files(repo_full_name: str, pr_number: int) -> List[str]:
    if not repo_full_name:
        return []
    headers = {
        "Accept": "application/vnd.github+json",
    }
    if GITHUB_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_ACCESS_TOKEN}"
    params = {"per_page": 100, "page": 1}
    filenames: List[str] = []
    while True:
        resp = requests.get(
            f"{API_BASE}/repos/{repo_full_name}/pulls/{pr_number}/files",
            headers=headers,
            params=params,
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("GitHub API files request failed (%s): %s", resp.status_code, resp.text)
            break
        data = resp.json()
        if not data:
            break
        filenames.extend(item.get("filename") for item in data if item.get("filename"))
        if len(data) < params["per_page"]:
            break
        params["page"] += 1
    return filenames
