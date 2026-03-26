"""Sprint analytics: all metric computations for the dashboard."""

from collections import defaultdict
from datetime import datetime, timedelta
from . import config


def compute(data):
    """
    Takes raw sprint data (from JiraClient.fetch_sprint_data) and returns
    a dict of all computed metrics for the dashboard.
    """
    sprint = data["target_sprint"]
    issues = data["issues"]
    prev_sprint = data.get("prev_sprint")
    prev_issues = data.get("prev_issues", [])
    velocity_sprints = data.get("velocity_sprints", [])
    next_sprint_meta = data.get("next_sprint")
    next_issues = data.get("next_issues", [])
    base_url = data.get("base_url", "")

    sp = config.SP_FIELD

    # ── Classify issues ──

    stories = [i for i in issues if i["fields"].get("issuetype", {}).get("name") != "Sub-task"]
    subtasks = [i for i in issues if i["fields"].get("issuetype", {}).get("name") == "Sub-task"]

    done_stories = [s for s in stories if _is_done(s)]
    done_subtasks = [s for s in subtasks if _is_done(s)]

    points_committed = sum(i["fields"].get(sp) or 0 for i in stories)
    points_completed = sum(i["fields"].get(sp) or 0 for i in done_stories)
    completion_rate = (points_completed / points_committed * 100) if points_committed > 0 else 0

    # ── Previous sprint velocity ──

    prev_stories = [i for i in prev_issues if i["fields"].get("issuetype", {}).get("name") != "Sub-task"]
    prev_done = [s for s in prev_stories if _is_done(s)]
    prev_committed = sum(i["fields"].get(sp) or 0 for i in prev_stories)
    prev_completed = sum(i["fields"].get(sp) or 0 for i in prev_done)

    # ── Parent-child map ──

    parent_map = defaultdict(list)
    for st in subtasks:
        parent_key = st["fields"].get("parent", {}).get("key") if st["fields"].get("parent") else None
        if parent_key:
            parent_map[parent_key].append(st)

    # ── Epic grouping ──

    epic_map = defaultdict(list)
    for s in stories:
        parent = s["fields"].get("parent")
        epic_name = parent.get("fields", {}).get("summary", "No Epic") if parent else "No Epic"
        epic_map[epic_name].append(s)

    # ── Contributor stats (proportional sub-task split) ──

    contributor_stats = defaultdict(lambda: {"points_share": 0.0, "subtasks_done": 0, "stories_owned": 0})

    for story in done_stories:
        pts = story["fields"].get(sp) or 0
        story_key = story["key"]
        story_assignee = story["fields"].get("assignee")
        story_assignee_name = story_assignee.get("displayName", "Unassigned") if story_assignee else "Unassigned"

        contributor_stats[story_assignee_name]["stories_owned"] += 1

        subs = parent_map.get(story_key, [])
        done_subs = [s for s in subs if _is_done(s)]

        if done_subs and pts > 0:
            assignee_counts = defaultdict(int)
            for sub in done_subs:
                a = sub["fields"].get("assignee")
                name = a.get("displayName", "Unassigned") if a else "Unassigned"
                assignee_counts[name] += 1
            total_done = sum(assignee_counts.values())
            for name, count in assignee_counts.items():
                contributor_stats[name]["points_share"] += pts * count / total_done
        elif pts > 0:
            contributor_stats[story_assignee_name]["points_share"] += pts

    for sub in done_subtasks:
        a = sub["fields"].get("assignee")
        name = a.get("displayName", "Unassigned") if a else "Unassigned"
        contributor_stats[name]["subtasks_done"] += 1

    sorted_contributors = sorted(contributor_stats.items(), key=lambda x: x[1]["points_share"], reverse=True)

    # ── Awards (only sub-task completers, exclude "Unassigned") ──

    eligible = [
        (n, s) for n, s in sorted_contributors
        if s["subtasks_done"] > 0 and n != "Unassigned"
    ]
    mvp = eligible[0] if eligible else None
    workhorse = max(eligible, key=lambda x: x[1]["subtasks_done"]) if eligible else None

    # Speed Demon: fastest avg sub-task cycle time
    subtask_ct = defaultdict(list)
    for sub in done_subtasks:
        a = sub["fields"].get("assignee")
        sname = a.get("displayName", "Unassigned") if a else "Unassigned"
        if sname == "Unassigned":
            continue
        changelog = sub.get("changelog", {}).get("histories", [])
        first_ip, last_d = None, None
        for h in changelog:
            for item in h.get("items", []):
                if item.get("field") == "status":
                    dt = _parse_ts(h["created"])
                    if dt is None:
                        continue
                    to_cat = item.get("to")
                    if _status_is_in_progress(item) and first_ip is None:
                        first_ip = dt
                    if item.get("toString") == "Done":
                        last_d = dt
        if first_ip and last_d and last_d > first_ip:
            days = max((last_d - first_ip).total_seconds() / 86400, 0.1)
            subtask_ct[sname].append(days)

    speed_demon = None
    for sname, times in subtask_ct.items():
        if contributor_stats[sname]["subtasks_done"] > 0:
            avg = sum(times) / len(times)
            if speed_demon is None or avg < speed_demon[1]:
                speed_demon = (sname, avg)

    # ── Cycle time (stories, using statusCategory) ──

    cycle_times = {}
    for story in done_stories:
        changelog = story.get("changelog", {}).get("histories", [])
        first_ip, last_d = None, None
        for h in changelog:
            for item in h.get("items", []):
                if item.get("field") == "status":
                    dt = _parse_ts(h["created"])
                    if dt is None:
                        continue
                    if _status_is_in_progress(item) and first_ip is None:
                        first_ip = dt
                    if item.get("toString") == "Done":
                        last_d = dt
        if first_ip and last_d and last_d > first_ip:
            cycle_times[story["key"]] = max((last_d - first_ip).days, 1)

    avg_cycle_time = sum(cycle_times.values()) / len(cycle_times) if cycle_times else 0

    # ── Burndown (with pre-sprint fix) ──

    sprint_start = sprint.get("startDate", "")[:10]
    sprint_end = sprint.get("endDate", "")[:10] if sprint.get("endDate") else ""
    burndown = {}

    if sprint_start and sprint_end:
        try:
            start_dt = datetime.strptime(sprint_start, "%Y-%m-%d")
            end_dt = datetime.strptime(sprint_end, "%Y-%m-%d")
        except (ValueError, TypeError):
            start_dt = end_dt = None

        if start_dt and end_dt:
            done_dates = {}
            for story in done_stories:
                pts = story["fields"].get(sp) or 0
                if pts == 0:
                    continue
                changelog = story.get("changelog", {}).get("histories", [])
                for h in changelog:
                    for item in h.get("items", []):
                        if item.get("field") == "status" and item.get("toString") == "Done":
                            done_dates[story["key"]] = h["created"][:10]

            # Pre-subtract stories done before sprint start
            remaining = points_committed
            for key, done_date in done_dates.items():
                try:
                    if datetime.strptime(done_date, "%Y-%m-%d") < start_dt:
                        pts = next((s["fields"].get(sp) or 0 for s in done_stories if s["key"] == key), 0)
                        remaining -= pts
                except (ValueError, TypeError):
                    pass

            current = start_dt
            while current <= end_dt:
                day_str = current.strftime("%Y-%m-%d")
                for key, done_date in done_dates.items():
                    if done_date == day_str:
                        pts = next((s["fields"].get(sp) or 0 for s in done_stories if s["key"] == key), 0)
                        remaining -= pts
                burndown[day_str] = max(remaining, 0)
                current += timedelta(days=1)

    # ── Bugs vs Planned Work ──

    bug_points = sum(
        s["fields"].get(sp) or 0 for s in stories
        if s["fields"].get("issuetype", {}).get("name", "") in config.BUG_ISSUE_TYPES
    )
    planned_points = sum(
        s["fields"].get(sp) or 0 for s in stories
        if s["fields"].get("issuetype", {}).get("name", "") not in config.BUG_ISSUE_TYPES
    )

    # ── Scope changes (added/removed mid-sprint) ──

    scope_changes = _detect_scope_changes(issues, sprint)

    # ── Velocity (all sprints including current) ──

    all_velocity = velocity_sprints + [{
        "name": sprint["name"],
        "id": sprint["id"],
        "committed": points_committed,
        "completed": points_completed,
    }]

    vel_delta = ""
    if prev_completed > 0:
        delta_pct = ((points_completed - prev_completed) / prev_completed) * 100
        if delta_pct > 0:
            vel_delta = f"+{delta_pct:.0f}% vs last sprint"
        elif delta_pct < 0:
            vel_delta = f"{delta_pct:.0f}% vs last sprint"
        else:
            vel_delta = "Same as last sprint"

    # ── Cast (sub-task completers only) ──

    cast_list = [name for name, _ in eligible[:6]]

    # ── Carry-over ──

    not_done_stories = [s for s in stories if not _is_done(s)]
    carryover = [
        {
            "key": s["key"],
            "summary": s["fields"].get("summary", ""),
            "status": s["fields"].get("status", {}).get("name", ""),
            "points": s["fields"].get(sp) or 0,
            "assignee": (s["fields"].get("assignee") or {}).get("displayName", "Unassigned"),
        }
        for s in not_done_stories
    ]

    # ── Narrative ──

    grade, grade_label = config.get_grade(completion_rate)
    goal_met = completion_rate >= config.GOAL_MET_THRESHOLD
    goal_text = sprint.get("goal", "")

    narrative = (
        f"This sprint, the team focused on <em>{_esc(goal_text or 'delivering value')}</em>. "
        f"They completed {len(done_stories)} of {len(stories)} stories "
        f"({points_completed:.0f} of {points_committed:.0f} points), "
        f"achieving a {completion_rate:.0f}% completion rate. "
    )
    if mvp:
        narrative += f"{mvp[0]} led the charge with {mvp[1]['points_share']:.1f} points across {mvp[1]['subtasks_done']} sub-tasks. "
    if prev_completed > 0:
        delta = ((points_completed - prev_completed) / prev_completed) * 100
        if delta > 0:
            narrative += f"Velocity is up {delta:.0f}% from last sprint."
        elif delta < 0:
            narrative += f"Velocity is down {abs(delta):.0f}% from last sprint."
        else:
            narrative += "Velocity is holding steady from last sprint."

    # ── Sprint date range ──

    sprint_date_range = ""
    if sprint.get("startDate"):
        try:
            sd = datetime.strptime(sprint["startDate"][:10], "%Y-%m-%d")
            ed = datetime.strptime(sprint["endDate"][:10], "%Y-%m-%d") if sprint.get("endDate") else None
            sprint_date_range = f'{sd.strftime("%b %d")} &mdash; {ed.strftime("%b %d, %Y") if ed else "ongoing"}'
        except (ValueError, TypeError):
            pass

    # ── Coming Attractions ──

    coming_next = []
    if next_sprint_meta and next_sprint_meta["id"] != sprint["id"]:
        for ni in next_issues:
            if ni["fields"].get("issuetype", {}).get("name") == "Sub-task":
                continue
            coming_next.append({
                "key": ni["key"],
                "summary": ni["fields"].get("summary", ""),
                "points": ni["fields"].get(sp) or 0,
                "assignee": (ni["fields"].get("assignee") or {}).get("displayName", "TBD"),
            })

    return {
        "sprint": sprint,
        "base_url": base_url,
        "stories": stories,
        "subtasks": subtasks,
        "done_stories": done_stories,
        "done_subtasks": done_subtasks,
        "points_committed": points_committed,
        "points_completed": points_completed,
        "completion_rate": completion_rate,
        "grade": grade,
        "grade_label": grade_label,
        "grade_color": _grade_color(completion_rate),
        "goal_met": goal_met,
        "goal_text": goal_text,
        "narrative": narrative,
        "sprint_date_range": sprint_date_range,
        "vel_delta": vel_delta,
        "cast_list": cast_list,
        "contributor_stats": contributor_stats,
        "sorted_contributors": sorted_contributors,
        "eligible": eligible,
        "mvp": mvp,
        "workhorse": workhorse,
        "speed_demon": speed_demon,
        "cycle_times": cycle_times,
        "avg_cycle_time": avg_cycle_time,
        "burndown": burndown,
        "all_velocity": all_velocity,
        "bug_points": bug_points,
        "planned_points": planned_points,
        "epic_map": dict(epic_map),
        "parent_map": dict(parent_map),
        "carryover": carryover,
        "scope_changes": scope_changes,
        "next_sprint": next_sprint_meta,
        "coming_next": coming_next,
        "prev_sprint": prev_sprint,
        "sprint_index": data.get("sprint_index", 0),
    }


# ── Helpers ──

def _is_done(issue):
    return issue["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"


def _parse_ts(ts_str):
    try:
        return datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None


def _status_is_in_progress(changelog_item):
    """Check if a status transition is to an 'In Progress' category status,
    rather than hardcoding the exact status name."""
    to_name = changelog_item.get("toString", "")
    # The changelog doesn't include statusCategory directly, so we check
    # common in-progress status names. The categoryId "4" = In Progress in Jira.
    in_progress_names = {
        "In Progress", "In Development", "In Review", "In QA",
        "In Testing", "Dev In Progress", "Code Review",
    }
    return to_name in in_progress_names


def _detect_scope_changes(issues, sprint):
    """Detect issues added or removed mid-sprint by checking changelog for Sprint field changes."""
    sprint_start = sprint.get("startDate", "")[:10]
    if not sprint_start:
        return {}

    try:
        start_dt = datetime.strptime(sprint_start, "%Y-%m-%d")
    except (ValueError, TypeError):
        return {}

    sprint_name = sprint.get("name", "")
    sprint_id = str(sprint.get("id", ""))
    changes = {}

    for issue in issues:
        changelog = issue.get("changelog", {}).get("histories", [])
        for h in changelog:
            ts = _parse_ts(h["created"])
            if ts is None or ts.date() <= start_dt.date():
                continue
            for item in h.get("items", []):
                if item.get("field") == "Sprint":
                    to_val = item.get("toString", "") or ""
                    from_val = item.get("fromString", "") or ""
                    if sprint_name in to_val or sprint_id in (item.get("to", "") or ""):
                        changes[issue["key"]] = "added_mid_sprint"
                    elif sprint_name in from_val:
                        changes[issue["key"]] = "removed_mid_sprint"

    return changes


def _grade_color(rate):
    if rate >= 70:
        return "#4ecca3"
    if rate >= 50:
        return "#f5c518"
    return "#e94560"


def _esc(s):
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
