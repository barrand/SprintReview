"""Jira REST API client with pagination and caching."""

import json
import os
import requests
from requests.auth import HTTPBasicAuth
from . import config


class JiraClient:
    def __init__(self, base_url=None, email=None, token=None):
        self.base_url = base_url or config.JIRA_BASE_URL
        self.auth = HTTPBasicAuth(email or config.JIRA_EMAIL, token or config.JIRA_API_TOKEN)
        self.headers = {"Accept": "application/json"}
        os.makedirs(config.CACHE_DIR, exist_ok=True)

    def _get(self, path, params=None):
        resp = requests.get(
            f"{self.base_url}{path}",
            auth=self.auth,
            headers=self.headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Sprint metadata ──

    def fetch_all_sprints(self, board_id, states="closed,active,future"):
        """Fetch all sprints for a board, paginated."""
        sprints = []
        start_at = 0
        while True:
            data = self._get(
                f"/rest/agile/1.0/board/{board_id}/sprint",
                {"state": states, "maxResults": 50, "startAt": start_at},
            )
            sprints.extend(data.get("values", []))
            if data.get("isLast", True) or len(sprints) >= data.get("total", 0):
                break
            start_at = len(sprints)
        return sprints

    def fetch_closed_sprints(self, board_id, limit=10):
        """Fetch the most recent N closed sprints (sorted by endDate)."""
        all_closed = self.fetch_all_sprints(board_id, states="closed")
        return all_closed[-limit:] if len(all_closed) > limit else all_closed

    def fetch_active_and_future(self, board_id):
        """Fetch active + future sprints (for 'Coming Attractions')."""
        try:
            data = self._get(
                f"/rest/agile/1.0/board/{board_id}/sprint",
                {"state": "active,future", "maxResults": 5},
            )
            return data.get("values", [])
        except Exception:
            return []

    # ── Issue fetching ──

    def fetch_sprint_issues(self, sprint_id, fields=None, expand=None, use_cache=False):
        """Fetch all issues for a sprint with pagination. Optionally cache results."""
        cache_path = os.path.join(config.CACHE_DIR, f"{sprint_id}.json")

        if use_cache and os.path.exists(cache_path):
            with open(cache_path) as f:
                return json.load(f)

        all_issues = []
        start_at = 0
        params = {"fields": fields or config.ISSUE_FIELDS, "maxResults": 100, "startAt": 0}
        if expand:
            params["expand"] = expand

        while True:
            params["startAt"] = start_at
            data = self._get(f"/rest/agile/1.0/sprint/{sprint_id}/issue", params)
            all_issues.extend(data.get("issues", []))
            total = data.get("total", 0)
            if len(all_issues) >= total:
                break
            start_at = len(all_issues)

        if use_cache:
            with open(cache_path, "w") as f:
                json.dump(all_issues, f, default=str)

        return all_issues

    def fetch_sprint_issues_lightweight(self, sprint_id, use_cache=False):
        """Fetch issues with minimal fields (for velocity calculations)."""
        return self.fetch_sprint_issues(
            sprint_id, fields=config.LIGHTWEIGHT_FIELDS, use_cache=use_cache
        )

    def fetch_sprint_issues_full(self, sprint_id, use_cache=False):
        """Fetch issues with all fields + changelog (for the target sprint)."""
        return self.fetch_sprint_issues(
            sprint_id,
            fields=config.ISSUE_FIELDS,
            expand="changelog",
            use_cache=use_cache,
        )

    # ── High-level data fetcher ──

    def fetch_sprint_data(self, board_id, target_sprint=None, sprint_count=6):
        """
        Fetch all data needed for a sprint review.
        Returns a dict with: target_sprint, issues, prev_sprint, prev_issues,
        velocity_sprints, next_sprint, next_issues, all_sprints, base_url.
        """
        print("Fetching sprint metadata...")
        closed = self.fetch_closed_sprints(board_id, limit=sprint_count)

        if not closed:
            raise ValueError("No closed sprints found for this board.")

        if target_sprint:
            target = next((s for s in closed if s["name"] == target_sprint), None)
            if not target:
                raise ValueError(f"Sprint '{target_sprint}' not found in closed sprints.")
        else:
            target = closed[-1]

        target_idx = next(i for i, s in enumerate(closed) if s["id"] == target["id"])
        prev = closed[target_idx - 1] if target_idx > 0 else None
        prev_of_prev_sprint = closed[target_idx - 2] if target_idx > 1 else None

        active_future = self.fetch_active_and_future(board_id)
        next_sprint = None
        if active_future:
            after_target = [s for s in active_future if s["id"] != target["id"]]
            next_sprint = after_target[0] if after_target else None

        print(f"Target sprint: {target['name']}")
        print(f"Fetching issues for '{target['name']}' (with changelogs)...")
        issues = self.fetch_sprint_issues_full(target["id"])
        print(f"  Got {len(issues)} issues")

        prev_issues = []
        if prev:
            print(f"Fetching issues for previous sprint '{prev['name']}'...")
            prev_issues = self.fetch_sprint_issues_lightweight(prev["id"], use_cache=True)
            print(f"  Got {len(prev_issues)} issues")

        velocity_sprints = []
        for s in closed:
            if s["id"] == target["id"]:
                continue
            if prev and s["id"] == prev["id"]:
                vel_issues = prev_issues
            else:
                print(f"Fetching velocity data for '{s['name']}'...")
                vel_issues = self.fetch_sprint_issues_lightweight(s["id"], use_cache=True)

            committed = sum(
                i["fields"].get(config.SP_FIELD) or 0
                for i in vel_issues
                if i["fields"].get("issuetype", {}).get("name") != "Sub-task"
            )
            completed = sum(
                i["fields"].get(config.SP_FIELD) or 0
                for i in vel_issues
                if i["fields"].get("issuetype", {}).get("name") != "Sub-task"
                and i["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"
            )
            velocity_sprints.append({
                "name": s["name"], "id": s["id"],
                "committed": committed, "completed": completed,
            })

        next_issues = []
        if next_sprint:
            print(f"Fetching issues for next sprint '{next_sprint['name']}'...")
            try:
                next_issues = self.fetch_sprint_issues_lightweight(next_sprint["id"])
                print(f"  Got {len(next_issues)} issues")
            except Exception as e:
                print(f"  Failed: {e}")

        return {
            "target_sprint": target,
            "issues": issues,
            "prev_sprint": prev,
            "prev_issues": prev_issues,
            "velocity_sprints": velocity_sprints,
            "next_sprint": next_sprint,
            "next_issues": next_issues,
            "all_sprints": closed,
            "base_url": self.base_url,
        }
