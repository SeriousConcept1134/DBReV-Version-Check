"""Runs only in GitHub Actions (see .github/workflows/check_nexus_version.yml) - never
shipped to end users. Queries the Nexus Mods API (authenticated with the author's own
personal API key, stored as the NEXUS_API_KEY repo secret) for this mod's current
version and changelog, and merges the result into version.json at the repo root, which
the app fetches unauthenticated via raw.githubusercontent.com.

Nexus's changelogs endpoint returns {"<version>": ["<html/text line>", ...]}, not the
{version, date, changes} shape this app wants, and it doesn't give a reliable per-version
date - so the newest entry's date falls back to the mod's file `updated_time`.
"""
import html
import json
import os
import re
import sys
import urllib.request

GAME_DOMAIN = "skyrimspecialedition"
MOD_ID = 184169
API_BASE = f"https://api.nexusmods.com/v1/games/{GAME_DOMAIN}/mods/{MOD_ID}"
VERSION_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "version.json")


def _api_get(url, api_key):
    req = urllib.request.Request(url, headers={"apikey": api_key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def _strip_html(text):
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _read_existing_version_json():
    if not os.path.isfile(VERSION_JSON_PATH):
        return {"latest_version": "", "nexus_updated_time": "", "changelog": []}
    with open(VERSION_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    api_key = os.environ.get("NEXUS_API_KEY")
    if not api_key:
        print("ERROR: NEXUS_API_KEY environment variable is not set.")
        return 1

    mod_info = _api_get(f"{API_BASE}.json", api_key)
    latest_version = mod_info.get("version")
    updated_time = mod_info.get("updated_time")
    if not latest_version:
        print("ERROR: Nexus API response did not include a 'version' field.")
        return 1

    existing = _read_existing_version_json()

    if existing.get("latest_version") == latest_version:
        print(f"version.json already up to date at {latest_version}; nothing to do.")
        return 0

    changelogs = _api_get(f"{API_BASE}/changelogs.json", api_key)
    raw_lines = changelogs.get(latest_version, [])
    changes = [_strip_html(line) for line in raw_lines if _strip_html(line)]
    if not changes:
        changes = ["No changelog details provided for this release."]

    new_entry = {
        "version": latest_version,
        "date": (updated_time or "")[:10],
        "changes": changes,
    }

    changelog = [new_entry] + [
        entry for entry in existing.get("changelog", []) if entry.get("version") != latest_version
    ]

    output = {
        "latest_version": latest_version,
        "nexus_updated_time": updated_time,
        "changelog": changelog,
    }

    with open(VERSION_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)
        f.write("\n")

    print(f"Updated version.json: latest_version is now {latest_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
