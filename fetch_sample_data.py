"""Fetch real sprint data for the sample HTML file. Uses most recently closed sprint."""

import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
EMAIL = os.getenv("JIRA_EMAIL", "").strip()
API_TOKEN = os.getenv("JIRA_API_TOKEN", "").strip()
BOARD_ID = 75
SP_FIELD = "customfield_10041"

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Accept": "application/json"}

def jira_get(path, params=None):
    resp = requests.get(f"{BASE_URL}{path}", auth=auth, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def fetch_all_issues(sprint_id, fields, expand=None):
    all_issues = []
    start_at = 0
    while True:
        params = {"fields": fields, "maxResults": 100, "startAt": start_at}
        if expand:
            params["expand"] = expand
        data = jira_get(f"/rest/agile/1.0/sprint/{sprint_id}/issue", params)
        all_issues.extend(data["issues"])
        print(f"  Fetched {len(all_issues)} / {data['total']}")
        if len(all_issues) >= data["total"]:
            break
        start_at = len(all_issues)
    return all_issues

# 1. Get all closed sprints + any active/future
print("Fetching sprint metadata...")
meta = jira_get(f"/rest/agile/1.0/board/{BOARD_ID}/sprint", {"state": "closed", "maxResults": 1})
total_closed = meta["total"]
sprints_data = jira_get(f"/rest/agile/1.0/board/{BOARD_ID}/sprint", {
    "state": "closed", "startAt": max(0, total_closed - 6), "maxResults": 6
})
closed_sprints = sprints_data["values"]
print(f"Got {len(closed_sprints)} closed sprints (of {total_closed} total)")
for s in closed_sprints:
    print(f"  [{s['state']}] {s['name']} (id={s['id']})")

latest = closed_sprints[-1]
previous = closed_sprints[-2] if len(closed_sprints) > 1 else None

# 2. Find active/future sprint for "Coming Attractions"
print("\nFetching active/future sprints...")
next_sprint = None
try:
    future_data = jira_get(f"/rest/agile/1.0/board/{BOARD_ID}/sprint", {"state": "active,future", "maxResults": 1})
    next_sprint = future_data["values"][0] if future_data.get("values") else None
except:
    pass
print(f"Next sprint: {next_sprint['name'] if next_sprint else 'None'}")

# 3. Fetch all issues for latest closed sprint (with changelogs)
FIELDS = f"summary,status,assignee,issuetype,priority,{SP_FIELD},parent,description,attachment"
print(f"\nFetching issues for '{latest['name']}' (with changelogs)...")
all_issues = fetch_all_issues(latest["id"], FIELDS, expand="changelog")

# 4. Fetch previous sprint (lightweight, for velocity)
prev_issues = []
if previous:
    print(f"\nFetching issues for previous sprint '{previous['name']}'...")
    prev_issues = fetch_all_issues(previous["id"], f"summary,status,issuetype,{SP_FIELD},assignee")

# 5. Fetch next sprint issues
next_issues = []
if next_sprint:
    print(f"\nFetching issues for next sprint '{next_sprint['name']}'...")
    try:
        data = jira_get(f"/rest/agile/1.0/sprint/{next_sprint['id']}/issue", {
            "fields": f"summary,status,issuetype,{SP_FIELD},assignee", "maxResults": 50,
        })
        next_issues = data.get("issues", [])
        print(f"  Got {len(next_issues)} issues")
    except Exception as e:
        print(f"  Failed: {e}")

# 6. Velocity data for the other closed sprints
velocity_sprints = []
for s in closed_sprints:
    if s["id"] == latest["id"]:
        continue
    if previous and s["id"] == previous["id"]:
        issues = prev_issues
    else:
        print(f"Fetching velocity data for '{s['name']}'...")
        data = jira_get(f"/rest/agile/1.0/sprint/{s['id']}/issue", {
            "fields": f"summary,status,issuetype,{SP_FIELD}", "maxResults": 200,
        })
        issues = data.get("issues", [])

    committed = sum(i["fields"].get(SP_FIELD) or 0 for i in issues if i["fields"].get("issuetype", {}).get("name") != "Sub-task")
    completed = sum(i["fields"].get(SP_FIELD) or 0 for i in issues
                    if i["fields"].get("issuetype", {}).get("name") != "Sub-task"
                    and i["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done")
    velocity_sprints.append({
        "name": s["name"], "id": s["id"],
        "committed": committed, "completed": completed,
    })

output = {
    "latest_sprint": latest,
    "previous_sprint": previous,
    "next_sprint": next_sprint,
    "issues": all_issues,
    "prev_issues": prev_issues,
    "next_issues": next_issues,
    "velocity_sprints": velocity_sprints,
    "base_url": BASE_URL,
}

os.makedirs("output", exist_ok=True)
with open("output/sample_data.json", "w") as f:
    json.dump(output, f, indent=2, default=str)

print(f"\nTarget sprint: {latest['name']}")
print(f"Saved to output/sample_data.json ({len(json.dumps(output, default=str)) // 1024} KB)")
print("Done!")
