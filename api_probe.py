"""
API Probe Script -- Tests Jira Cloud API endpoints needed for Sprint Review automation.
Run this after filling in your .env file to verify connectivity and field names.
"""

import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
EMAIL = os.getenv("JIRA_EMAIL", "")
API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
BOARD_ID = 75

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Accept": "application/json"}


def probe(label, method, url, **kwargs):
    print(f"\n{'='*60}")
    print(f"PROBE: {label}")
    print(f"  {method} {url}")
    try:
        resp = requests.request(method, url, auth=auth, headers=headers, timeout=15, **kwargs)
        print(f"  Status: {resp.status_code}")
        if resp.status_code >= 400:
            print(f"  Error: {resp.text[:500]}")
            return None
        data = resp.json()
        print(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else f'array[{len(data)}]'}")
        return data
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def dump_sample(data, label, max_depth=3):
    """Pretty-print a sample of the data."""
    print(f"\n--- {label} (sample) ---")
    print(json.dumps(data, indent=2, default=str)[:3000])
    if len(json.dumps(data, default=str)) > 3000:
        print("  ... (truncated)")


# ── Test 1: Auth + Board Info ──
print("\n" + "#"*60)
print("# JIRA API PROBE - Sprint Review Automation")
print(f"# Base URL: {BASE_URL}")
print(f"# Email: {EMAIL}")
print(f"# Board ID: {BOARD_ID}")
print("#"*60)

board = probe("Get Board Info", "GET", f"{BASE_URL}/rest/agile/1.0/board/{BOARD_ID}")
if board:
    dump_sample(board, "Board")

# ── Test 2: List Sprints ──
sprints_data = probe(
    "List Sprints (active + closed)",
    "GET",
    f"{BASE_URL}/rest/agile/1.0/board/{BOARD_ID}/sprint?state=active,closed&maxResults=5"
)

latest_sprint = None
previous_sprint = None
if sprints_data and "values" in sprints_data:
    sprints = sprints_data["values"]
    print(f"\n  Found {len(sprints)} sprints (showing up to 5):")
    for s in sprints:
        print(f"    - [{s['state']}] {s['name']} (id={s['id']})")
    if sprints:
        latest_sprint = sprints[-1]
        if len(sprints) > 1:
            previous_sprint = sprints[-2]
        dump_sample(latest_sprint, "Latest Sprint")

# ── Test 3: Sprint Issues ──
if latest_sprint:
    fields = "summary,status,assignee,issuetype,priority,description,attachment,comment,customfield_10016,customfield_10028,customfield_10004"
    issues_data = probe(
        f"Get Issues for Sprint '{latest_sprint['name']}' (id={latest_sprint['id']})",
        "GET",
        f"{BASE_URL}/rest/agile/1.0/sprint/{latest_sprint['id']}/issue?fields={fields}&maxResults=5&expand=changelog"
    )

    if issues_data and "issues" in issues_data:
        issues = issues_data["issues"]
        print(f"\n  Total issues in sprint: {issues_data.get('total', '?')}")
        print(f"  Returned in this page: {len(issues)}")

        if issues:
            first_issue = issues[0]
            dump_sample(first_issue, "First Issue (full)")

            # Inspect available fields to find story points
            print("\n--- Field inspection (first issue) ---")
            fields_obj = first_issue.get("fields", {})
            print(f"  Available field keys: {sorted(fields_obj.keys())}")

            # Check common story point field names
            for field_name in ["customfield_10016", "customfield_10028", "customfield_10004", "story_points"]:
                val = fields_obj.get(field_name)
                if val is not None:
                    print(f"  {field_name} = {val} (LIKELY STORY POINTS)")

            # Check status structure
            status = fields_obj.get("status", {})
            print(f"\n  Status: {status.get('name', '?')}")
            print(f"  Status Category: {status.get('statusCategory', {}).get('name', '?')}")

            # Check assignee structure
            assignee = fields_obj.get("assignee")
            if assignee:
                print(f"  Assignee: {assignee.get('displayName', '?')} ({assignee.get('accountId', '?')})")
            else:
                print("  Assignee: Unassigned")

            # Check attachments
            attachments = fields_obj.get("attachment", [])
            print(f"  Attachments: {len(attachments)}")
            for att in attachments[:3]:
                print(f"    - {att.get('filename')} ({att.get('mimeType')}, {att.get('size')} bytes)")

            # Check issue type
            itype = fields_obj.get("issuetype", {})
            print(f"  Issue Type: {itype.get('name', '?')}")

            # Check epic (customfield_10004 or via the agile endpoint)
            epic = fields_obj.get("customfield_10004")
            if epic:
                print(f"  Epic: {epic}")

            # Check changelog if expanded
            changelog = first_issue.get("changelog")
            if changelog:
                print(f"\n  Changelog entries: {changelog.get('total', '?')}")
                for entry in changelog.get("histories", [])[:3]:
                    print(f"    [{entry.get('created', '?')}] by {entry.get('author', {}).get('displayName', '?')}:")
                    for item in entry.get("items", []):
                        print(f"      {item.get('field')}: {item.get('fromString')} -> {item.get('toString')}")

    # ── Test 4: Bulk Changelog ──
    if issues_data and "issues" in issues_data:
        issue_ids = [int(i["id"]) for i in issues_data["issues"][:3]]
        changelog_data = probe(
            "Bulk Fetch Changelogs (first 3 issues)",
            "POST",
            f"{BASE_URL}/rest/api/3/changelog/bulkfetch",
            json={"issueIds": issue_ids, "maxResults": 10}
        )
        if changelog_data:
            dump_sample(changelog_data, "Bulk Changelog Response")

# ── Test 5: Try getting all fields to find story points ──
fields_list = probe(
    "List All Fields (to find story points field ID)",
    "GET",
    f"{BASE_URL}/rest/api/3/field"
)
if fields_list and isinstance(fields_list, list):
    print(f"\n  Total fields: {len(fields_list)}")
    print("\n  Fields matching 'point' or 'story' or 'estimate':")
    for f in fields_list:
        name = (f.get("name") or "").lower()
        if any(kw in name for kw in ["point", "story", "estimate", "velocity"]):
            print(f"    {f.get('id')}: {f.get('name')} (custom={f.get('custom', False)})")

print("\n" + "="*60)
print("PROBE COMPLETE")
print("="*60)
