"""Generate a sample HTML sprint review from real Jira data."""

import json
import os
import random
from datetime import datetime, timedelta
from collections import defaultdict

with open("output/sample_data.json") as f:
    data = json.load(f)

sprint = data["latest_sprint"]
issues = data["issues"]
prev_sprint = data["previous_sprint"]
prev_issues = data["prev_issues"]
velocity_sprints = data["velocity_sprints"]
next_sprint_meta = data["next_sprint"]
next_issues = data["next_issues"]
BASE_URL = data["base_url"]
SP_FIELD = "customfield_10041"

# ── Analytics ──

stories = [i for i in issues if i["fields"].get("issuetype", {}).get("name") not in ("Sub-task",)]
subtasks = [i for i in issues if i["fields"].get("issuetype", {}).get("name") == "Sub-task"]

done_stories = [s for s in stories if s["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"]
done_subtasks = [s for s in subtasks if s["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"]

points_committed = sum(i["fields"].get(SP_FIELD) or 0 for i in stories)
points_completed = sum(i["fields"].get(SP_FIELD) or 0 for i in done_stories)
completion_rate = (points_completed / points_committed * 100) if points_committed > 0 else 0

# Previous sprint velocity
prev_stories = [i for i in prev_issues if i["fields"].get("issuetype", {}).get("name") not in ("Sub-task",)]
prev_done = [s for s in prev_stories if s["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"]
prev_committed = sum(i["fields"].get(SP_FIELD) or 0 for i in prev_stories)
prev_completed = sum(i["fields"].get(SP_FIELD) or 0 for i in prev_done)

# Build parent-child map
parent_map = defaultdict(list)
for st in subtasks:
    parent_key = st["fields"].get("parent", {}).get("key") if st["fields"].get("parent") else None
    if parent_key:
        parent_map[parent_key].append(st)

# Epic grouping
epic_map = defaultdict(list)
for s in stories:
    parent = s["fields"].get("parent")
    epic_name = parent.get("fields", {}).get("summary", "No Epic") if parent else "No Epic"
    epic_map[epic_name].append(s)

# Contributor stats (sub-task split)
contributor_stats = defaultdict(lambda: {"points_share": 0.0, "subtasks_done": 0, "stories_owned": 0, "cycle_times": []})

for story in done_stories:
    pts = story["fields"].get(SP_FIELD) or 0
    story_key = story["key"]
    story_assignee = story["fields"].get("assignee", {})
    story_assignee_name = story_assignee.get("displayName", "Unassigned") if story_assignee else "Unassigned"
    
    contributor_stats[story_assignee_name]["stories_owned"] += 1
    
    subs = parent_map.get(story_key, [])
    done_subs = [s for s in subs if s["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"]
    
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

# Cycle time from changelog (for stories)
cycle_times = {}
for story in done_stories:
    changelog = story.get("changelog", {}).get("histories", [])
    first_in_progress = None
    last_done = None
    for h in changelog:
        for item in h.get("items", []):
            if item.get("field") == "status":
                ts = h["created"][:19]
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                except:
                    continue
                if item.get("toString") in ("In Progress",) and first_in_progress is None:
                    first_in_progress = dt
                if item.get("toString") == "Done":
                    last_done = dt
    if first_in_progress and last_done:
        days = (last_done - first_in_progress).days
        cycle_times[story["key"]] = max(days, 1)

avg_cycle_time = sum(cycle_times.values()) / len(cycle_times) if cycle_times else 0

# Burndown data
sprint_start = sprint.get("startDate", "")[:10]
sprint_end = sprint.get("endDate", "")[:10] if sprint.get("endDate") else ""

burndown = {}
if sprint_start and sprint_end:
    try:
        start_dt = datetime.strptime(sprint_start, "%Y-%m-%d")
        end_dt = datetime.strptime(sprint_end, "%Y-%m-%d")
    except:
        start_dt = end_dt = None
    
    if start_dt and end_dt:
        done_dates = {}
        for story in done_stories:
            pts = story["fields"].get(SP_FIELD) or 0
            if pts == 0:
                continue
            changelog = story.get("changelog", {}).get("histories", [])
            for h in changelog:
                for item in h.get("items", []):
                    if item.get("field") == "status" and item.get("toString") == "Done":
                        done_dates[story["key"]] = h["created"][:10]
        
        current = start_dt
        remaining = points_committed
        while current <= end_dt:
            day_str = current.strftime("%Y-%m-%d")
            for key, done_date in done_dates.items():
                if done_date == day_str:
                    pts = next((s["fields"].get(SP_FIELD) or 0 for s in done_stories if s["key"] == key), 0)
                    remaining -= pts
            burndown[day_str] = max(remaining, 0)
            current += timedelta(days=1)

# Bugs vs Planned Work (at story level, by points)
bug_types = {"Defect", "Bug"}
bug_points = sum(s["fields"].get(SP_FIELD) or 0 for s in stories if s["fields"].get("issuetype", {}).get("name", "") in bug_types)
planned_points = sum(s["fields"].get(SP_FIELD) or 0 for s in stories if s["fields"].get("issuetype", {}).get("name", "") not in bug_types)
bug_count = sum(1 for s in stories if s["fields"].get("issuetype", {}).get("name", "") in bug_types)
planned_count = sum(1 for s in stories if s["fields"].get("issuetype", {}).get("name", "") not in bug_types)

# Awards -- only people who completed sub-tasks are eligible
sorted_contributors = sorted(contributor_stats.items(), key=lambda x: x[1]["points_share"], reverse=True)
eligible = [(n, s) for n, s in sorted_contributors if s["subtasks_done"] > 0]
mvp = eligible[0] if eligible else ("Nobody", {"points_share": 0, "subtasks_done": 0, "stories_owned": 0})
workhorse = max(eligible, key=lambda x: x[1]["subtasks_done"]) if eligible else ("Nobody", {"points_share": 0, "subtasks_done": 0, "stories_owned": 0})

# Speed Demon: fastest avg sub-task cycle time (not story-level)
subtask_ct = defaultdict(list)
for sub in done_subtasks:
    a = sub["fields"].get("assignee")
    sname = a.get("displayName", "Unassigned") if a else "Unassigned"
    changelog = sub.get("changelog", {}).get("histories", [])
    first_ip, last_d = None, None
    for h in changelog:
        for item in h.get("items", []):
            if item.get("field") == "status":
                ts = h["created"][:19]
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                except:
                    continue
                if item.get("toString") == "In Progress" and first_ip is None:
                    first_ip = dt
                if item.get("toString") == "Done":
                    last_d = dt
    if first_ip and last_d:
        days = max((last_d - first_ip).total_seconds() / 86400, 0.1)
        subtask_ct[sname].append(days)

fastest_cycle = None
for sname, times in subtask_ct.items():
    if contributor_stats[sname]["subtasks_done"] > 0:
        avg = sum(times) / len(times)
        if fastest_cycle is None or avg < fastest_cycle[1]:
            fastest_cycle = (sname, avg)

speed_demon = fastest_cycle if fastest_cycle else ("N/A", 0)

# Velocity for all sprints including current
all_velocity = velocity_sprints + [{
    "name": sprint["name"],
    "id": sprint["id"],
    "committed": points_committed,
    "completed": points_completed,
}]

# Velocity delta
vel_delta = ""
if prev_completed > 0:
    delta_pct = ((points_completed - prev_completed) / prev_completed) * 100
    if delta_pct > 0:
        vel_delta = f"+{delta_pct:.0f}% vs last sprint"
    elif delta_pct < 0:
        vel_delta = f"{delta_pct:.0f}% vs last sprint"
    else:
        vel_delta = "Same as last sprint"

# Cast (contributors sorted by points)
cast_list = ", ".join([name for name, _ in sorted_contributors[:6]])

# Carry-over
not_done_stories = [s for s in stories if s["fields"].get("status", {}).get("statusCategory", {}).get("name") != "Done"]
carryover = [(s["key"], s["fields"].get("summary", ""), s["fields"].get("status", {}).get("name", ""), 
              s["fields"].get(SP_FIELD) or 0,
              s["fields"].get("assignee", {}).get("displayName", "Unassigned") if s["fields"].get("assignee") else "Unassigned")
             for s in not_done_stories if s["fields"].get(SP_FIELD)]

# Narrative
narrative = (
    f"This sprint, the team focused on <em>{sprint.get('goal', 'delivering value')}</em>. "
    f"They completed {len(done_stories)} of {len(stories)} stories "
    f"({points_completed:.0f} of {points_committed:.0f} points), "
    f"achieving a {completion_rate:.0f}% completion rate. "
)
if mvp[0] != "Nobody":
    narrative += f"{mvp[0]} led the charge with {mvp[1]['points_share']:.1f} points across {mvp[1]['subtasks_done']} sub-tasks. "
if prev_completed > 0:
    delta = ((points_completed - prev_completed) / prev_completed) * 100
    if delta > 0:
        narrative += f"Velocity is up {delta:.0f}% from last sprint."
    elif delta < 0:
        narrative += f"Velocity is down {abs(delta):.0f}% from last sprint."
    else:
        narrative += "Velocity is holding steady from last sprint."

# Letter grade
def get_grade(rate):
    if rate >= 95: return ("A+", "Instant Classic")
    if rate >= 90: return ("A", "Certified Fresh")
    if rate >= 85: return ("A-", "Critics' Choice")
    if rate >= 80: return ("B+", "Crowd Pleaser")
    if rate >= 75: return ("B", "Worth the Ticket")
    if rate >= 70: return ("B-", "Solid Matinee")
    if rate >= 60: return ("C+", "Mixed Reviews")
    if rate >= 50: return ("C", "Needs a Sequel")
    if rate >= 40: return ("D", "Straight to DVD")
    return ("F", "Box Office Bomb")

grade, grade_label = get_grade(completion_rate)
grade_color = "#4ecca3" if completion_rate >= 70 else "#f5c518" if completion_rate >= 50 else "#e94560"

# Sprint goal verdict
goal_met = completion_rate >= 70
goal_text = sprint.get("goal", "")

# ── HTML Generation ──

def esc(s):
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def _first_sentence(text):
    """Return the first sentence (up to ~150 chars) from a block of text."""
    if not text:
        return ""
    import re
    m = re.match(r"(.+?[.!?])\s", text)
    sentence = m.group(1) if m else text
    if len(sentence) > 150:
        sentence = sentence[:147] + "..."
    return sentence

def issue_link(key):
    return f'<a href="{BASE_URL}/browse/{key}" target="_blank">{esc(key)}</a>'

# Burndown chart data
burndown_labels = json.dumps(list(burndown.keys()))
burndown_values = json.dumps(list(burndown.values()))
if burndown:
    ideal_step = points_committed / max(len(burndown) - 1, 1)
    ideal_values = json.dumps([round(points_committed - ideal_step * i, 1) for i in range(len(burndown))])
else:
    ideal_values = "[]"

# Velocity chart data
vel_labels = json.dumps([v["name"].replace("FS02: ", "") for v in all_velocity])
vel_committed = json.dumps([v["committed"] for v in all_velocity])
vel_completed = json.dumps([v["completed"] for v in all_velocity])

# Contributor chart data
contrib_labels = json.dumps([name for name, _ in sorted_contributors[:8]])
contrib_points = json.dumps([round(s["points_share"], 1) for _, s in sorted_contributors[:8]])
contrib_subtasks = json.dumps([s["subtasks_done"] for _, s in sorted_contributors[:8]])

# Bugs vs Planned chart data
work_split_labels = json.dumps(["Defects / Bugs", "Planned Work"])
work_split_values = json.dumps([bug_points, planned_points])

DEMO_GIFS = [
    "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmVhazlpM2psOGd4OGNycjNzc2dhOGlra3BuNHJjdHFtdTdtbjZ0ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3oKIPnAiaMCJ8HOLZK/giphy.gif",
    "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHg3Nmhvc25qOXJ0ZjBhMjk0c2N2ZGRoNjRtcnQ2Z2tkZmthOXIyZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/26tn33aiTi1jkl6H6/giphy.gif",
    "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExMHBnbzF0emhkYWJ1MXp5NnZrOHIzb3c5bDR0enRhZWtyaGY5NHdlOCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/L1R1tvI9svkIWwpVYr/giphy.gif",
    "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExMTI2amVhdHRqZm12N2M2Ymd6NGRjdmdlYXFjNXhodjUxdGU4OWdwbyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/qgQUggAC3Pfv687qPC/giphy.gif",
    "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWxiYnZlYTk1MWtjdzI4MXhoZzhkd3h2MjBjdDk5cTBiOTh2NzNlaSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/bGgsc5mWoryfgKBx1u/giphy.gif",
    "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2Q4cWF1ZGg3N3Vpb2x0cDg5ZDZ0dTdyNXFibDF3cGl0cGQ4OWlhMSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/RbDKaczqWovIugyJmW/giphy.gif",
    "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZjVya2FhaTN0ZW44bHNhMTZvenBhOXM3MjBobGszZXdxMW5rMnFlYiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xT9IgzoKnwFNmISR8I/giphy.gif",
    "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExdmV2NjZyemFlaWVzOTBvd3FxN3AwMnE3cGRrczRzZGJ5dG5qbDRiaSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/13HgwGsXF0aiGY/giphy.gif",
]

# Build completed work HTML
completed_html = ""
story_idx = 0
all_done_keys = [
    s["key"]
    for epic_stories in epic_map.values()
    for s in epic_stories
    if s["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"
]
demo_rng = random.Random(hash(sprint["name"]))
demo_count = min(demo_rng.randint(3, 4), len(all_done_keys))
demo_keys = set(demo_rng.sample(all_done_keys, demo_count))

for epic_name, epic_stories in epic_map.items():
    done_in_epic = [s for s in epic_stories if s["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"]
    if not done_in_epic:
        continue
    completed_html += f'<h3 class="epic-title">{esc(epic_name)}</h3>\n'
    for story in done_in_epic:
        key = story["key"]
        summary = esc(story["fields"].get("summary", ""))
        pts = story["fields"].get(SP_FIELD) or 0
        assignee = story["fields"].get("assignee")
        assignee_name = esc(assignee.get("displayName", "Unassigned")) if assignee else "Unassigned"
        desc = story["fields"].get("description")
        desc_text = ""
        if desc and isinstance(desc, dict):
            for block in desc.get("content", []):
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        desc_text += item.get("text", "")
            desc_text = desc_text[:200] + "..." if len(desc_text) > 200 else desc_text

        subs = parent_map.get(key, [])
        subs_html = ""
        for sub in subs:
            sub_status = sub["fields"].get("status", {}).get("statusCategory", {}).get("name", "")
            sub_icon = "done" if sub_status == "Done" else "wip"
            sub_assignee = sub["fields"].get("assignee")
            sub_assignee_name = esc(sub_assignee.get("displayName", "")) if sub_assignee else ""
            subs_html += f'    <div class="subtask {sub_icon}"><span class="check">{"&#10003;" if sub_status == "Done" else "&#9711;"}</span> {issue_link(sub["key"])}: {esc(sub["fields"].get("summary", ""))} <span class="sub-assignee">{sub_assignee_name}</span></div>\n'

        sub_count = len(subs)
        caption = _first_sentence(desc_text) or summary

        if key in demo_keys:
            gif_url = DEMO_GIFS[story_idx % len(DEMO_GIFS)]
            demo_block = f'  <p class="demo-caption">{esc(caption)}</p>\n  <div class="demo-section">\n    <img src="{gif_url}" alt="Feature demo for {esc(key)}" class="demo-gif" loading="lazy">\n  </div>'
        else:
            demo_block = ""

        completed_html += f'''<div class="story-card" data-story-key="{esc(key)}">
  <div class="story-header">
    <button class="feature-star-btn" data-key="{esc(key)}" title="Pick as your favorite feature">&#9734;</button>
    <span class="story-key">{issue_link(key)}</span>
    <span class="story-summary">{summary}</span>
    <span class="story-meta">{pts:.0f} pts &middot; {assignee_name}</span>
  </div>
{demo_block}
  <details>
    <summary class="subtask-toggle">View {sub_count} subtask{"s" if sub_count != 1 else ""}</summary>
    <div class="subtask-list">
{subs_html}    </div>
  </details>
</div>\n'''
        story_idx += 1

# Carry-over HTML
carryover_html = ""
for key, summary, status, pts, assignee in carryover:
    carryover_html += f'<tr><td>{issue_link(key)}</td><td>{esc(summary)}</td><td><span class="status-badge">{esc(status)}</span></td><td>{pts:.0f}</td><td>{esc(assignee)}</td></tr>\n'

# Coming Attractions Ballot
next_html = ""
if next_sprint_meta and next_sprint_meta["id"] != sprint["id"]:
    next_html += f'<h2 class="section-title">Coming Attractions Ballot &mdash; {esc(next_sprint_meta["name"])}</h2>\n'
    next_html += f'<p class="tagline">Cast your votes for next sprint\'s top priorities</p>\n'
    if next_sprint_meta.get("goal"):
        next_html += f'<p><strong>Sprint Goal:</strong> {esc(next_sprint_meta["goal"])}</p>\n'
    next_html += '<div class="ballot-container" id="ballotContainer">\n'
    for ni in next_issues[:10]:
        ni_assignee = ni["fields"].get("assignee")
        ni_name = esc(ni_assignee.get("displayName", "TBD")) if ni_assignee else "TBD"
        if ni["fields"].get("issuetype", {}).get("name") == "Sub-task":
            continue
        ni_key = ni["key"]
        ni_pts = ni["fields"].get(SP_FIELD) or "-"
        ni_summary = esc(ni["fields"].get("summary", ""))
        next_html += f'''<div class="ballot-item" data-key="{esc(ni_key)}" id="ballot-{esc(ni_key)}">
  <button class="ballot-vote-btn" data-key="{esc(ni_key)}">
    <span class="ballot-arrow">&#9650;</span>
    <span class="ballot-vote-count" id="count-{esc(ni_key)}">0</span>
  </button>
  <div class="ballot-info">
    <div class="ballot-title">
      {issue_link(ni_key)} &middot; {ni_summary}
      <span class="ballot-badge top-pick" id="badge-{esc(ni_key)}" style="display:none">top pick</span>
      <span class="ballot-badge voted-badge" id="voted-{esc(ni_key)}" style="display:none">voted</span>
    </div>
    <div class="ballot-meta">{ni_pts} pts &middot; {ni_name}</div>
    <div class="ballot-bar-track">
      <div class="ballot-bar-fill" id="bar-{esc(ni_key)}" style="width:0%"></div>
    </div>
  </div>
</div>\n'''
    next_html += '</div>\n'
    next_html += '<div class="ballot-footer" id="ballotFooter">Click &#9650; to vote &middot; Click again to unvote</div>\n'

# Contributors table (awards only for eligible sub-task completers)
contrib_table = ""
for name, stats in sorted_contributors[:10]:
    highlight = ""
    if stats["subtasks_done"] > 0:
        if name == mvp[0]:
            highlight = "MVP"
        elif name == workhorse[0]:
            highlight = "Workhorse"
        elif fastest_cycle and name == speed_demon[0]:
            highlight = "Speed Demon"
    contrib_table += f'<tr data-member="{esc(name)}"><td><strong>{esc(name)}</strong></td><td>{stats["points_share"]:.1f}</td><td>{stats["subtasks_done"]}</td><td>{stats["stories_owned"]}</td><td><span class="award-badge">{highlight}</span></td><td><button class="cast-vote-btn" data-member="{esc(name)}">&#9995; High 5</button></td></tr>\n'

sprint_date_range = ""
if sprint.get("startDate"):
    try:
        sd = datetime.strptime(sprint["startDate"][:10], "%Y-%m-%d")
        ed = datetime.strptime(sprint["endDate"][:10], "%Y-%m-%d") if sprint.get("endDate") else None
        sprint_date_range = f'{sd.strftime("%b %d")} &mdash; {ed.strftime("%b %d, %Y") if ed else "ongoing"}'
    except:
        sprint_date_range = ""

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sprint Review: {esc(sprint["name"])}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --bg: #0f0f0f;
    --surface: #1a1a2e;
    --surface2: #16213e;
    --accent: #e94560;
    --accent2: #0f3460;
    --gold: #f5c518;
    --text: #e0e0e0;
    --text-muted: #888;
    --success: #4ecca3;
    --warning: #f0a500;
    --border: #2a2a4a;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ 
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text);
    line-height: 1.6; padding: 0;
  }}
  .hero {{
    background: linear-gradient(135deg, var(--surface) 0%, var(--accent2) 100%);
    padding: 60px 40px; text-align: center;
    border-bottom: 3px solid var(--accent);
  }}
  .hero h1 {{ font-size: 2.8em; font-weight: 300; letter-spacing: 2px; }}
  .hero h1 strong {{ font-weight: 700; color: var(--gold); }}
  .hero .date {{ color: var(--text-muted); font-size: 1.1em; margin-top: 8px; }}
  .hero .cast {{ color: var(--text-muted); font-style: italic; margin-top: 16px; }}
  .goal-card {{
    max-width: 720px; margin: 32px auto 0 auto;
    background: var(--surface); border-radius: 16px;
    padding: 32px 40px; text-align: center;
    border: 1px solid var(--border);
  }}
  .goal-card .goal-label {{
    font-size: 0.75em; text-transform: uppercase; letter-spacing: 3px;
    color: var(--text-muted); margin-bottom: 12px;
  }}
  .goal-card .goal-text {{
    font-size: 1.15em; font-style: italic; margin-bottom: 16px;
    line-height: 1.6; color: var(--text);
  }}
  .goal-card .goal-summary {{
    font-size: 0.95em; color: var(--text-muted); margin-bottom: 20px;
    line-height: 1.5;
  }}
  .progress-track {{
    width: 100%; height: 14px; background: var(--surface2);
    border-radius: 7px; overflow: hidden; margin-bottom: 8px;
  }}
  .progress-fill {{
    height: 100%; border-radius: 7px;
    transition: width 0.5s ease;
  }}
  .progress-stats {{
    font-size: 0.95em; color: var(--text-muted); margin-bottom: 24px;
  }}
  .grade-big {{
    font-size: 3.6em; font-weight: 900; letter-spacing: 2px;
    line-height: 1;
  }}
  .grade-label-big {{
    font-size: 1.1em; font-weight: 700; text-transform: uppercase;
    letter-spacing: 3px; margin-top: 4px; margin-bottom: 20px;
  }}
  .goal-status {{
    font-size: 1.2em; font-weight: 700; letter-spacing: 1px;
    margin-bottom: 24px;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 20px; }}
  .section-title {{
    font-size: 1.6em; font-weight: 600; margin: 48px 0 20px 0;
    padding-bottom: 8px; border-bottom: 2px solid var(--accent);
    color: var(--gold); letter-spacing: 1px;
  }}
  .trailer {{
    background: var(--surface); border-left: 4px solid var(--gold);
    padding: 24px 30px; margin: 24px 0; border-radius: 0 8px 8px 0;
    font-size: 1.1em; font-style: italic; color: var(--text);
  }}
  .kpi-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px; margin: 24px 0;
  }}
  .kpi-card {{
    background: var(--surface); border-radius: 12px; padding: 20px;
    text-align: center; border: 1px solid var(--border);
  }}
  .kpi-card .value {{ font-size: 2em; font-weight: 700; color: var(--gold); }}
  .kpi-card .label {{ font-size: 0.85em; color: var(--text-muted); margin-top: 4px; }}
  .awards-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px; margin: 24px 0;
  }}
  .award-card {{
    background: var(--surface); border-radius: 12px; padding: 24px;
    border: 1px solid var(--gold); text-align: center;
  }}
  .award-gif {{
    width: 100%; height: 160px; object-fit: cover;
    border-radius: 8px; margin-bottom: 16px;
  }}
  .award-card .award-name {{ color: var(--gold); font-size: 0.85em; text-transform: uppercase; letter-spacing: 2px; }}
  .award-card .winner {{ font-size: 1.4em; font-weight: 700; margin: 8px 0; }}
  .award-card .reason {{ color: var(--text-muted); font-size: 0.9em; }}
  .streak-alert {{
    background: linear-gradient(135deg, #1a3a1a, #0f2f0f);
    border: 1px solid var(--success); border-radius: 8px;
    padding: 16px 24px; margin: 16px 0; text-align: center;
    color: var(--success); font-weight: 600;
  }}
  .chart-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
    gap: 24px; margin: 24px 0;
  }}
  .chart-card {{
    background: var(--surface); border-radius: 12px; padding: 24px;
    border: 1px solid var(--border);
  }}
  .chart-card h3 {{ color: var(--text-muted); font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }}
  .fresh-list {{ list-style: none; margin: 16px 0; }}
  .fresh-list li {{
    padding: 12px 16px; margin: 8px 0;
    background: var(--surface); border-radius: 8px;
    border-left: 3px solid var(--success);
  }}
  .epic-title {{
    color: var(--gold); font-size: 1.2em; margin: 32px 0 16px 0;
    padding: 8px 0; border-bottom: 1px solid var(--border);
  }}
  .story-card {{
    background: var(--surface); border-radius: 10px; margin: 16px 0;
    border: 1px solid var(--border); overflow: hidden;
  }}
  .story-header {{
    padding: 16px 20px; display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
  }}
  .demo-caption {{
    padding: 10px 20px 0 20px; margin: 0; color: var(--text-muted);
    font-size: 0.92em; font-style: italic; line-height: 1.5;
  }}
  .demo-gif {{
    width: 100%; max-height: 340px; object-fit: cover; border-radius: 0;
    display: block;
  }}
  .subtask-toggle {{
    padding: 10px 20px; font-size: 0.85em; color: var(--text-muted);
    cursor: pointer; list-style: none; border-top: 1px solid var(--border);
  }}
  .subtask-toggle::-webkit-details-marker {{ display: none; }}
  .subtask-toggle::before {{
    content: '\\25B6'; font-size: 0.65em; margin-right: 8px;
    display: inline-block; transition: transform 0.2s;
  }}
  details[open] > .subtask-toggle::before {{ transform: rotate(90deg); }}
  .subtask-toggle:hover {{ color: var(--gold); }}
  .story-key a {{ color: var(--gold); text-decoration: none; font-weight: 600; }}
  .story-key a:hover {{ text-decoration: underline; }}
  .story-summary {{ flex: 1; font-weight: 500; }}
  .story-meta {{ color: var(--text-muted); font-size: 0.9em; }}
  .subtask-list {{ padding: 12px 20px; }}
  .subtask {{ padding: 4px 0; font-size: 0.9em; color: var(--text-muted); }}
  .subtask.done {{ color: var(--text); }}
  .subtask a {{ color: var(--text-muted); text-decoration: none; }}
  .subtask a:hover {{ color: var(--gold); }}
  .check {{ margin-right: 6px; }}
  .subtask.done .check {{ color: var(--success); }}
  .sub-assignee {{ color: var(--text-muted); font-size: 0.85em; margin-left: 4px; }}
  .demo-section {{
    padding: 16px 20px; background: var(--surface2); border-top: 1px solid var(--border);
  }}
  .demo-label {{ font-weight: 600; font-size: 0.9em; color: var(--gold); }}
  .demo-desc {{ color: var(--text-muted); font-size: 0.9em; margin: 8px 0; }}
  .screenshot-placeholder {{
    border: 2px dashed var(--border); border-radius: 8px; padding: 40px;
    text-align: center; color: var(--text-muted); font-style: italic;
    margin-top: 12px;
  }}
  .data-table {{
    width: 100%; border-collapse: collapse; margin: 16px 0;
    background: var(--surface); border-radius: 8px; overflow: hidden;
  }}
  .data-table th {{
    background: var(--surface2); padding: 12px 16px; text-align: left;
    font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px;
    color: var(--text-muted);
  }}
  .data-table td {{ padding: 10px 16px; border-top: 1px solid var(--border); }}
  .data-table a {{ color: var(--gold); text-decoration: none; }}
  .data-table a:hover {{ text-decoration: underline; }}
  .status-badge {{
    background: var(--accent2); padding: 2px 10px; border-radius: 12px;
    font-size: 0.85em;
  }}
  .award-badge {{
    background: var(--gold); color: var(--bg); padding: 2px 10px;
    border-radius: 12px; font-size: 0.8em; font-weight: 600;
  }}
  .tagline {{ color: var(--text-muted); font-style: italic; margin-bottom: 16px; }}
  .gif-container {{ text-align: center; margin: 20px 0; }}
  .gif-container img {{ max-width: 400px; border-radius: 12px; }}
  .footer {{
    text-align: center; padding: 40px; color: var(--text-muted);
    border-top: 1px solid var(--border); margin-top: 60px; font-size: 0.9em;
  }}
  @media (max-width: 600px) {{
    .hero h1 {{ font-size: 1.8em; }}
    .chart-grid {{ grid-template-columns: 1fr; }}
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}

  /* Feature Star Vote */
  .feature-star-btn {{
    background: none; border: none; cursor: pointer; font-size: 1.3em;
    color: var(--text-muted); transition: all 0.2s; padding: 0 4px;
    line-height: 1; flex-shrink: 0;
  }}
  .feature-star-btn:hover {{ color: var(--gold); transform: scale(1.2); }}
  .feature-star-btn.selected {{ color: var(--gold); text-shadow: 0 0 8px rgba(245,197,24,0.5); }}
  .feature-fav-banner {{
    background: linear-gradient(135deg, rgba(245,197,24,0.1), rgba(245,197,24,0.05));
    border: 1px solid var(--gold); border-radius: 12px; padding: 16px 24px;
    margin: 16px 0 24px 0; text-align: center; color: var(--gold);
    font-size: 0.95em; display: none;
  }}
  .feature-fav-banner.visible {{ display: block; animation: fadeInUp 0.3s ease; }}

  /* Cast High-5 Vote */
  .cast-vote-btn {{
    background: none; border: 2px solid var(--border); border-radius: 8px;
    cursor: pointer; padding: 6px 14px; color: var(--text-muted);
    font-size: 0.95em; transition: all 0.2s; white-space: nowrap;
  }}
  .cast-vote-btn:hover {{ border-color: var(--gold); color: var(--gold); }}
  .cast-vote-btn.selected {{
    border-color: var(--gold); background: var(--gold); color: var(--bg); font-weight: 700;
  }}
  .cast-fav-banner {{
    background: linear-gradient(135deg, rgba(245,197,24,0.1), rgba(245,197,24,0.05));
    border: 1px solid var(--gold); border-radius: 12px; padding: 16px 24px;
    margin: 0 0 16px 0; text-align: center; color: var(--gold);
    font-size: 0.95em; display: none;
  }}
  .cast-fav-banner.visible {{ display: block; animation: fadeInUp 0.3s ease; }}

  /* Ticket Stub */
  .ticket-stub {{
    max-width: 680px; margin: 48px auto 0 auto; padding: 32px 40px;
    background: var(--surface); border: 2px dashed var(--gold);
    border-radius: 16px; text-align: center; position: relative;
  }}
  .ticket-stub.locked {{ border-color: var(--border); opacity: 0.7; }}
  .ticket-stub.locked .ticket-header {{ color: var(--text-muted); }}
  .ticket-progress {{ margin-bottom: 20px; }}
  .ticket-progress-title {{
    font-size: 0.85em; text-transform: uppercase; letter-spacing: 2px;
    color: var(--text-muted); margin-bottom: 12px;
  }}
  .ticket-steps {{ display: flex; gap: 24px; justify-content: center; flex-wrap: wrap; }}
  .ticket-step {{
    display: flex; align-items: center; gap: 8px; font-size: 0.9em;
    color: var(--text-muted); transition: color 0.3s;
  }}
  .ticket-step.done {{ color: var(--success); }}
  .ticket-step-icon {{
    width: 24px; height: 24px; border-radius: 50%; border: 2px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7em; transition: all 0.3s;
  }}
  .ticket-step.done .ticket-step-icon {{
    border-color: var(--success); background: var(--success); color: var(--bg);
  }}
  .ticket-header {{
    font-size: 1.4em; font-weight: 900; letter-spacing: 6px;
    text-transform: uppercase; color: var(--gold); margin-bottom: 4px;
  }}
  .ticket-perforation {{ border-top: 2px dashed var(--border); margin: 16px -40px; }}
  .ticket-body {{ padding-top: 8px; }}
  .ticket-checkin label {{
    display: block; font-size: 0.85em; text-transform: uppercase;
    letter-spacing: 2px; color: var(--text-muted); margin-bottom: 12px;
  }}
  .ticket-input-row {{
    display: flex; gap: 12px; justify-content: center; margin-bottom: 20px;
  }}
  .ticket-input-row input {{
    flex: 1; max-width: 300px; padding: 10px 16px; border-radius: 8px;
    border: 1px solid var(--border); background: var(--surface2);
    color: var(--text); font-size: 1em; outline: none; transition: border-color 0.2s;
  }}
  .ticket-input-row input:focus {{ border-color: var(--gold); }}
  .ticket-input-row button {{
    padding: 10px 24px; border-radius: 8px; border: 2px solid var(--gold);
    background: transparent; color: var(--gold); font-weight: 700;
    font-size: 0.95em; cursor: pointer; letter-spacing: 1px; transition: all 0.2s;
  }}
  .ticket-input-row button:hover {{ background: var(--gold); color: var(--bg); }}
  .ticket-confirmed {{
    font-size: 1.2em; font-weight: 600; margin-bottom: 20px;
    animation: fadeInUp 0.4s ease;
  }}
  .ticket-check {{ color: var(--success); font-size: 1.3em; margin-right: 8px; }}
  .ticket-checkin.tear-away {{ animation: tearAway 0.4s ease forwards; }}
  .ticket-attendance {{ margin-top: 16px; }}
  .ticket-count {{
    font-size: 0.9em; color: var(--text-muted); margin-bottom: 16px; letter-spacing: 1px;
  }}
  .ticket-avatars {{
    display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;
  }}
  .ticket-avatar {{
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    animation: fadeInUp 0.3s ease;
  }}
  .ticket-initials {{
    width: 48px; height: 48px; border-radius: 50%; background: var(--surface2);
    border: 2px solid var(--gold); display: flex; align-items: center;
    justify-content: center; font-weight: 700; font-size: 0.9em; color: var(--gold);
  }}
  .ticket-name {{
    font-size: 0.75em; color: var(--text-muted); max-width: 64px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .ticket-avatar.pending {{ opacity: 0.35; }}
  .ticket-avatar.pending .ticket-initials {{
    border-style: dashed; background: transparent; color: var(--text-muted);
    border-color: var(--text-muted);
  }}

  /* Coming Attractions Ballot */
  .ballot-container {{ display: flex; flex-direction: column; margin: 24px 0; }}
  .ballot-item {{
    display: flex; align-items: flex-start; gap: 16px; padding: 16px 20px;
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    margin: 6px 0; transition: border-color 0.2s, order 0.3s;
  }}
  .ballot-item:hover {{ border-color: var(--gold); }}
  .ballot-vote-btn {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-width: 56px; height: 56px; border-radius: 12px; border: 2px solid var(--border);
    background: transparent; cursor: pointer; transition: all 0.2s; gap: 2px; flex-shrink: 0;
  }}
  .ballot-vote-btn:hover {{ border-color: var(--gold); background: rgba(245,197,24,0.1); }}
  .ballot-vote-btn.voted {{ border-color: var(--gold); background: var(--gold); }}
  .ballot-arrow {{ font-size: 1.1em; color: var(--text-muted); transition: color 0.2s; line-height: 1; }}
  .ballot-vote-btn:hover .ballot-arrow {{ color: var(--gold); }}
  .ballot-vote-btn.voted .ballot-arrow {{ color: var(--bg); }}
  .ballot-vote-count {{ font-size: 0.85em; font-weight: 700; color: var(--text-muted); line-height: 1; }}
  .ballot-vote-btn.voted .ballot-vote-count {{ color: var(--bg); }}
  .ballot-info {{ flex: 1; min-width: 0; }}
  .ballot-title {{ font-weight: 500; margin-bottom: 4px; }}
  .ballot-title a {{ color: var(--gold); text-decoration: none; font-weight: 600; }}
  .ballot-title a:hover {{ text-decoration: underline; }}
  .ballot-meta {{ font-size: 0.85em; color: var(--text-muted); margin-bottom: 8px; }}
  .ballot-bar-track {{ height: 6px; background: var(--surface2); border-radius: 3px; overflow: hidden; }}
  .ballot-bar-fill {{ height: 100%; background: var(--gold); border-radius: 3px; transition: width 0.4s ease; }}
  .ballot-badge {{
    display: inline-block; font-size: 0.7em; padding: 2px 8px; border-radius: 10px;
    font-weight: 600; vertical-align: middle; margin-left: 8px;
  }}
  .ballot-badge.top-pick {{ background: rgba(245,197,24,0.2); color: var(--gold); border: 1px solid var(--gold); }}
  .ballot-badge.voted-badge {{ background: rgba(78,204,163,0.2); color: var(--success); border: 1px solid var(--success); }}
  .ballot-footer {{
    text-align: center; padding: 16px; font-size: 0.9em; color: var(--text-muted);
    border-top: 1px solid var(--border); margin-top: 8px;
  }}

  /* Feedback Box */
  .feedback-box {{
    max-width: 800px; margin: 24px auto 0 auto;
    background: var(--surface); border-radius: 16px; padding: 32px 40px;
    border: 1px solid var(--border);
  }}
  .feedback-prompt {{
    color: var(--text-muted); font-size: 0.95em; margin-bottom: 24px;
    text-align: center; line-height: 1.5;
  }}
  .feedback-entries {{ margin-bottom: 24px; }}
  .feedback-entry {{
    background: var(--surface2); border-radius: 10px; padding: 16px 20px;
    margin-bottom: 12px; border: 1px solid var(--border);
    animation: fadeInUp 0.3s ease;
  }}
  .feedback-entry-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 8px;
  }}
  .feedback-author {{ font-weight: 600; color: var(--gold); font-size: 0.9em; }}
  .feedback-time {{ color: var(--text-muted); font-size: 0.8em; }}
  .feedback-entry-text {{ color: var(--text); font-size: 0.95em; line-height: 1.5; }}
  .feedback-form {{ display: flex; flex-direction: column; gap: 12px; }}
  .feedback-name-input, .feedback-form textarea {{
    width: 100%; padding: 12px 16px; border-radius: 8px;
    border: 1px solid var(--border); background: var(--surface2);
    color: var(--text); font-size: 0.95em; font-family: inherit;
    outline: none; transition: border-color 0.2s; resize: vertical;
  }}
  .feedback-name-input:focus, .feedback-form textarea:focus {{ border-color: var(--gold); }}
  .feedback-form button {{
    align-self: flex-end; padding: 10px 32px; border-radius: 8px;
    border: 2px solid var(--gold); background: transparent;
    color: var(--gold); font-weight: 700; font-size: 0.95em;
    cursor: pointer; letter-spacing: 1px; transition: all 0.2s;
  }}
  .feedback-form button:hover {{ background: var(--gold); color: var(--bg); }}
  .feedback-empty {{
    text-align: center; color: var(--text-muted); font-style: italic;
    padding: 16px 0; font-size: 0.9em;
  }}

  @keyframes tearAway {{
    0% {{ opacity: 1; transform: translateY(0); max-height: 100px; }}
    100% {{ opacity: 0; transform: translateY(-20px); max-height: 0; overflow: hidden; margin: 0; padding: 0; }}
  }}
  @keyframes fadeInUp {{
    0% {{ opacity: 0; transform: translateY(10px); }}
    100% {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes pulse {{
    0% {{ transform: scale(1); }}
    50% {{ transform: scale(1.15); }}
    100% {{ transform: scale(1); }}
  }}
</style>
</head>
<body>

<div class="hero">
  <h1>Now Showing: <strong>{esc(sprint["name"])}</strong></h1>
  <div class="date">{sprint_date_range} &middot; A Mobile Masters Production</div>

  <div class="goal-card">
    <div class="goal-label">Sprint Goal</div>
    <div class="goal-text">&ldquo;{esc(goal_text)}&rdquo;</div>
    <div class="goal-summary">Completed {len(done_stories)} of {len(stories)} stories this sprint. {len(carryover)} {"story" if len(carryover) == 1 else "stories"} carried over to the next sprint.</div>
    <div class="progress-track">
      <div class="progress-fill" style="width:{completion_rate:.0f}%;background:{grade_color};"></div>
    </div>
    <div class="progress-stats">{points_completed:.0f} of {points_committed:.0f} points &middot; {completion_rate:.0f}% complete{f" &middot; {vel_delta}" if vel_delta else ""}</div>
    <div class="goal-status" style="color:{"#4ecca3" if goal_met else "#e94560"};">{"&#10003; GOAL ACHIEVED" if goal_met else "&#10007; GOAL NOT MET"}</div>
    <div class="grade-big" style="color:{grade_color};">{grade}</div>
    <div class="grade-label-big" style="color:{grade_color};">{esc(grade_label)}</div>
  </div>

  <div class="cast">Starring: {esc(cast_list)}</div>
</div>

<div class="container">

  <h2 class="section-title">The Trailer: Sprint Narrative</h2>
  <div class="trailer">{narrative}</div>

  <h2 class="section-title">Box Office Numbers: Sprint Metrics</h2>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="value">{len(done_stories)}/{len(stories)}</div>
      <div class="label">Stories Completed</div>
    </div>
    <div class="kpi-card">
      <div class="value">{points_completed:.0f}/{points_committed:.0f}</div>
      <div class="label">Story Points</div>
    </div>
    <div class="kpi-card">
      <div class="value">{completion_rate:.0f}%</div>
      <div class="label">Completion Rate</div>
    </div>
    <div class="kpi-card">
      <div class="value">{len(done_subtasks)}/{len(subtasks)}</div>
      <div class="label">Sub-tasks Done</div>
    </div>
    <div class="kpi-card">
      <div class="value">{avg_cycle_time:.1f}d</div>
      <div class="label">Avg Cycle Time</div>
    </div>
    <div class="kpi-card">
      <div class="value">{len(carryover)}</div>
      <div class="label">Carried Over</div>
    </div>
  </div>

  <h2 class="section-title">Fresh Releases: What's New in the Product</h2>
  <ul class="fresh-list">
'''

for story in done_stories[:8]:
    summary = story["fields"].get("summary", "")
    html += f'    <li><strong>{esc(summary)}</strong></li>\n'

html += f'''  </ul>

  <h2 class="section-title">The Academy Awards: Sprint Celebrations</h2>
  <div class="awards-grid">
    <div class="award-card">
      <img class="award-gif" src="https://media.giphy.com/media/lXo8uSnIkaB9e/giphy.gif" alt="Iron Man Suit Up">
      <div class="award-name">MVP</div>
      <div class="winner">{esc(mvp[0])}</div>
      <div class="reason">{mvp[1]["points_share"]:.1f} points &middot; {mvp[1]["subtasks_done"]} sub-tasks</div>
    </div>
    <div class="award-card">
      <img class="award-gif" src="https://media.giphy.com/media/ICoxhc8wGbJ8k/giphy.gif" alt="The Flash Running">
      <div class="award-name">Speed Demon</div>
      <div class="winner">{esc(speed_demon[0])}</div>
      <div class="reason">Avg {speed_demon[1]:.1f} day cycle time</div>
    </div>
    <div class="award-card">
      <img class="award-gif" src="https://media.giphy.com/media/yoJC2JaiEMoxIhQhY4/giphy.gif" alt="Rocky Training">
      <div class="award-name">Workhorse</div>
      <div class="winner">{esc(workhorse[0])}</div>
      <div class="reason">{workhorse[1]["subtasks_done"]} sub-tasks completed</div>
    </div>
  </div>

  <h2 class="section-title">Behind the Scenes: Charts &amp; Analytics</h2>
  <div class="chart-grid">
    <div class="chart-card">
      <h3>Burndown</h3>
      <canvas id="burndownChart"></canvas>
    </div>
    <div class="chart-card">
      <h3>Velocity Trend</h3>
      <canvas id="velocityChart"></canvas>
    </div>
    <div class="chart-card">
      <h3>Contributor Points</h3>
      <canvas id="contribChart"></canvas>
    </div>
    <div class="chart-card">
      <h3>Bugs vs Planned Work (Story Points)</h3>
      <canvas id="workSplitChart"></canvas>
    </div>
  </div>

  <h2 class="section-title">It's a Wrap: Completed Work</h2>
  <p style="color:var(--text-muted);margin-bottom:8px;">&#9734; Click the star on your favorite feature release</p>
  <div class="feature-fav-banner" id="featureFavBanner"></div>
  {completed_html}

  <h2 class="section-title">The Cast: Team Contributions</h2>
  <p style="color:var(--text-muted);margin-bottom:8px;">Give a High 5 to the team member who earned it this sprint</p>
  <div class="cast-fav-banner" id="castFavBanner"></div>
  <table class="data-table" id="castTable">
    <thead><tr><th>Contributor</th><th>Points</th><th>Sub-tasks</th><th>Stories Owned</th><th>Award</th><th>High 5</th></tr></thead>
    <tbody>{contrib_table}</tbody>
  </table>

  <h2 class="section-title">Left on the Cutting Room Floor: Carry-Over</h2>
  <table class="data-table">
    <thead><tr><th>Issue</th><th>Summary</th><th>Status</th><th>Points</th><th>Assignee</th></tr></thead>
    <tbody>{carryover_html if carryover_html else "<tr><td colspan='5' style='text-align:center;color:var(--text-muted)'>Nothing left behind. Clean sweep!</td></tr>"}</tbody>
  </table>

  {next_html}

  <div class="ticket-stub locked" id="ticketStub" data-sprint="{esc(sprint["name"])}">
    <div class="ticket-header">ADMIT ONE</div>
    <div class="ticket-perforation"></div>
    <div class="ticket-body">
      <div class="ticket-progress" id="ticketProgress">
        <div class="ticket-progress-title">Complete these steps to check in</div>
        <div class="ticket-steps">
          <div class="ticket-step" id="stepFeature">
            <span class="ticket-step-icon">1</span> Pick a favorite feature
          </div>
          <div class="ticket-step" id="stepCast">
            <span class="ticket-step-icon">2</span> High-5 a team member
          </div>
        </div>
      </div>
      <div class="ticket-checkin" id="ticketCheckin" style="display:none;">
        <label>Enter your name to mark attendance</label>
        <div class="ticket-input-row">
          <input type="text" id="ticketName" placeholder="Your name..." />
          <button id="ticketTear">&#9986; Tear Ticket</button>
        </div>
      </div>
      <div class="ticket-confirmed" id="ticketConfirmed" style="display:none;">
        <span class="ticket-check">&#10003;</span> You&rsquo;re checked in, <strong id="ticketWho"></strong>
      </div>
      <div class="ticket-attendance">
        <div class="ticket-count"><span id="attendeeCount">0</span> attended this screening</div>
        <div class="ticket-avatars" id="ticketAvatars"></div>
      </div>
    </div>
  </div>

  <h2 class="section-title">Post-Credits: Questions &amp; Feedback</h2>
  <div class="feedback-box" id="feedbackBox">
    <p class="feedback-prompt">Got a question about something that shipped? Feedback on a feature? Something the team should know? Drop it here.</p>
    <div class="feedback-entries" id="feedbackEntries"></div>
    <div class="feedback-form" id="feedbackForm">
      <input type="text" id="feedbackName" placeholder="Your name" class="feedback-name-input" />
      <textarea id="feedbackText" placeholder="Write your question or feedback..." rows="3"></textarea>
      <button id="feedbackSubmit">Submit</button>
    </div>
  </div>

</div>

<div class="footer">
  Generated automatically by Sprint Review Automation &middot; {datetime.now().strftime("%B %d, %Y")}
</div>

<script>
const chartDefaults = {{
  color: '#888',
  borderColor: '#2a2a4a',
}};
Chart.defaults.color = '#888';
Chart.defaults.borderColor = '#2a2a4a';

new Chart(document.getElementById('burndownChart'), {{
  type: 'line',
  data: {{
    labels: {burndown_labels},
    datasets: [
      {{
        label: 'Ideal',
        data: {ideal_values},
        borderColor: '#444',
        borderDash: [5, 5],
        pointRadius: 0,
        tension: 0,
      }},
      {{
        label: 'Actual',
        data: {burndown_values},
        borderColor: '#e94560',
        backgroundColor: 'rgba(233,69,96,0.1)',
        fill: true,
        tension: 0.1,
        pointRadius: 3,
        pointBackgroundColor: '#e94560',
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    scales: {{
      x: {{ ticks: {{ maxTicksLimit: 10 }} }},
      y: {{ beginAtZero: true, title: {{ display: true, text: 'Story Points Remaining' }} }}
    }}
  }}
}});

new Chart(document.getElementById('velocityChart'), {{
  type: 'bar',
  data: {{
    labels: {vel_labels},
    datasets: [
      {{
        label: 'Committed',
        data: {vel_committed},
        backgroundColor: 'rgba(15,52,96,0.8)',
        borderRadius: 4,
      }},
      {{
        label: 'Completed',
        data: {vel_completed},
        backgroundColor: 'rgba(245,197,24,0.8)',
        borderRadius: 4,
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    scales: {{
      y: {{ beginAtZero: true, title: {{ display: true, text: 'Story Points' }} }}
    }}
  }}
}});

new Chart(document.getElementById('contribChart'), {{
  type: 'bar',
  data: {{
    labels: {contrib_labels},
    datasets: [
      {{
        label: 'Points Share',
        data: {contrib_points},
        backgroundColor: 'rgba(245,197,24,0.8)',
        borderRadius: 4,
      }},
      {{
        label: 'Sub-tasks Done',
        data: {contrib_subtasks},
        backgroundColor: 'rgba(78,204,163,0.6)',
        borderRadius: 4,
      }}
    ]
  }},
  options: {{
    responsive: true,
    indexAxis: 'y',
    plugins: {{ legend: {{ position: 'bottom' }} }},
  }}
}});

new Chart(document.getElementById('workSplitChart'), {{
  type: 'doughnut',
  data: {{
    labels: {work_split_labels},
    datasets: [{{
      data: {work_split_values},
      backgroundColor: ['#e94560', '#4ecca3'],
      borderWidth: 0,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'bottom' }},
      tooltip: {{
        callbacks: {{
          label: function(ctx) {{
            return ctx.label + ': ' + ctx.parsed + ' pts';
          }}
        }}
      }}
    }},
  }}
}});

// ── Shared State ──
var SPRINT = (document.getElementById('ticketStub') || {{}}).dataset ? document.getElementById('ticketStub').dataset.sprint : 'default';
var STAKEHOLDERS = ["Jack Thompson","Bill Martinez","Gary Chen","Jenna Park","Sarah Williams","Mike O'Brien","Lisa Kumar","Tom Nguyen","Rachel Adams","Derek Foster","Amy Collins","Bryce Barrand"];
var PRESEEDED = ["Jack Thompson","Bill Martinez","Bryce Barrand"];
var CURRENT_USER = 'Bryce Barrand';
function lsGet(k, fallback) {{ try {{ return JSON.parse(localStorage.getItem(k)) || fallback; }} catch(e) {{ return fallback; }} }}
function lsSet(k, v) {{ localStorage.setItem(k, JSON.stringify(v)); }}

// Seed attendance on first load
(function() {{
  var seedKey = 'sr_seeded2_' + SPRINT;
  if (!localStorage.getItem(seedKey)) {{
    lsSet('sr_attendees_' + SPRINT, PRESEEDED);
    localStorage.setItem('sr_ticket_' + SPRINT, CURRENT_USER);
    localStorage.setItem(seedKey, '1');
  }}
}})();

// ── Feature Star Vote ──
(function() {{
  var fKey = 'sr_fav_feature_' + SPRINT;
  var stars = document.querySelectorAll('.feature-star-btn');
  if (!stars.length) return;

  function render() {{
    var fav = localStorage.getItem(fKey);
    stars.forEach(function(btn) {{
      var sel = btn.dataset.key === fav;
      btn.classList.toggle('selected', sel);
      btn.innerHTML = sel ? '&#9733;' : '&#9734;';
    }});
    var banner = document.getElementById('featureFavBanner');
    if (banner && fav) {{
      var card = document.querySelector('.story-card[data-story-key="' + fav + '"]');
      var title = card ? card.querySelector('.story-summary').textContent.trim() : fav;
      banner.innerHTML = '&#9733; Your Audience Choice: <strong>' + title + '</strong>';
      banner.classList.add('visible');
    }}
    updateTicketGate();
  }}

  document.addEventListener('click', function(e) {{
    var btn = e.target.closest('.feature-star-btn');
    if (!btn) return;
    e.preventDefault(); e.stopPropagation();
    var current = localStorage.getItem(fKey);
    if (current === btn.dataset.key) {{ localStorage.removeItem(fKey); }}
    else {{ localStorage.setItem(fKey, btn.dataset.key); }}
    btn.style.animation = 'pulse 0.3s ease';
    setTimeout(function(){{ btn.style.animation = ''; }}, 300);
    render();
  }});

  render();
}})();

// ── Cast High-5 Vote ──
(function() {{
  var cKey = 'sr_fav_cast_' + SPRINT;
  var btns = document.querySelectorAll('.cast-vote-btn');
  if (!btns.length) return;

  function render() {{
    var fav = localStorage.getItem(cKey);
    btns.forEach(function(btn) {{
      var sel = btn.dataset.member === fav;
      btn.classList.toggle('selected', sel);
      btn.innerHTML = sel ? '&#9733; High 5!' : '&#9995; High 5';
    }});
    var banner = document.getElementById('castFavBanner');
    if (banner && fav) {{
      banner.innerHTML = '&#9995; Fan Favorite: <strong>' + fav + '</strong>';
      banner.classList.add('visible');
    }} else if (banner) {{
      banner.classList.remove('visible');
    }}
    updateTicketGate();
  }}

  document.getElementById('castTable').addEventListener('click', function(e) {{
    var btn = e.target.closest('.cast-vote-btn');
    if (!btn) return;
    var current = localStorage.getItem(cKey);
    if (current === btn.dataset.member) {{ localStorage.removeItem(cKey); }}
    else {{ localStorage.setItem(cKey, btn.dataset.member); }}
    btn.style.animation = 'pulse 0.3s ease';
    setTimeout(function(){{ btn.style.animation = ''; }}, 300);
    render();
  }});

  render();
}})();

// ── Ticket Stub (engagement-gated) ──
function updateTicketGate() {{
  var stub = document.getElementById('ticketStub');
  if (!stub) return;
  var hasFeat = !!localStorage.getItem('sr_fav_feature_' + SPRINT);
  var hasCast = !!localStorage.getItem('sr_fav_cast_' + SPRINT);
  var isCheckedIn = !!localStorage.getItem('sr_ticket_' + SPRINT);

  var stepFeat = document.getElementById('stepFeature');
  var stepCast = document.getElementById('stepCast');
  if (stepFeat) stepFeat.classList.toggle('done', hasFeat);
  if (stepCast) stepCast.classList.toggle('done', hasCast);
  if (stepFeat) stepFeat.querySelector('.ticket-step-icon').innerHTML = hasFeat ? '&#10003;' : '1';
  if (stepCast) stepCast.querySelector('.ticket-step-icon').innerHTML = hasCast ? '&#10003;' : '2';

  var unlocked = hasFeat && hasCast;
  stub.classList.toggle('locked', !unlocked && !isCheckedIn);

  if (isCheckedIn) {{
    document.getElementById('ticketProgress').style.display = 'none';
    document.getElementById('ticketCheckin').style.display = 'none';
    document.getElementById('ticketConfirmed').style.display = 'block';
    document.getElementById('ticketWho').textContent = localStorage.getItem('sr_ticket_' + SPRINT);
  }} else if (unlocked) {{
    document.getElementById('ticketProgress').style.display = 'none';
    document.getElementById('ticketCheckin').style.display = 'block';
  }} else {{
    document.getElementById('ticketProgress').style.display = 'block';
    document.getElementById('ticketCheckin').style.display = 'none';
  }}
}}

(function() {{
  var stub = document.getElementById('ticketStub');
  if (!stub) return;
  var tKey = 'sr_ticket_' + SPRINT;
  var aKey = 'sr_attendees_' + SPRINT;

  function initials(n) {{
    return n.split(/\\s+/).map(function(w){{ return w[0]; }}).join('').toUpperCase().slice(0,2);
  }}
  function firstName(n) {{ return n.split(/\\s+/)[0]; }}

  function renderAvatars() {{
    var attendees = lsGet(aKey, []);
    var total = STAKEHOLDERS.length;
    var count = attendees.length;
    document.getElementById('attendeeCount').textContent = count + ' of ' + total;
    document.getElementById('ticketAvatars').innerHTML = STAKEHOLDERS.map(function(n) {{
      var active = attendees.indexOf(n) > -1;
      var cls = active ? 'ticket-avatar' : 'ticket-avatar pending';
      return '<div class="' + cls + '"><div class="ticket-initials">' + initials(n) +
        '</div><div class="ticket-name">' + firstName(n) + '</div></div>';
    }}).join('');
  }}

  function checkIn(name) {{
    localStorage.setItem(tKey, name);
    var list = lsGet(aKey, []);
    if (list.indexOf(name) === -1) {{ list.push(name); lsSet(aKey, list); }}
    var el = document.getElementById('ticketCheckin');
    el.classList.add('tear-away');
    setTimeout(function() {{
      el.style.display = 'none';
      document.getElementById('ticketConfirmed').style.display = 'block';
      document.getElementById('ticketWho').textContent = name;
      stub.classList.remove('locked');
      renderAvatars();
    }}, 400);
  }}

  renderAvatars();
  updateTicketGate();

  document.getElementById('ticketTear').addEventListener('click', function() {{
    var name = document.getElementById('ticketName').value.trim();
    if (name) checkIn(name);
  }});
  document.getElementById('ticketName').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') {{ var name = this.value.trim(); if (name) checkIn(name); }}
  }});
}})();

// ── Coming Attractions Ballot ──
(function() {{
  var container = document.getElementById('ballotContainer');
  if (!container) return;
  var stub = document.getElementById('ticketStub');
  var sprint = stub ? stub.dataset.sprint : 'default';
  var vKey = 'sr_votes_' + sprint;
  var mKey = 'sr_my_votes_' + sprint;

  function getVotes() {{ return JSON.parse(localStorage.getItem(vKey) || '{{}}'); }}
  function getMyVotes() {{ return JSON.parse(localStorage.getItem(mKey) || '[]'); }}
  function save(v, m) {{ localStorage.setItem(vKey, JSON.stringify(v)); localStorage.setItem(mKey, JSON.stringify(m)); }}

  function render() {{
    var votes = getVotes(), myVotes = getMyVotes();
    var vals = Object.values(votes);
    var maxV = Math.max.apply(null, [1].concat(vals));
    var entries = Object.entries(votes).sort(function(a,b){{ return b[1]-a[1]; }});
    var topKey = entries.length && entries[0][1] > 0 ? entries[0][0] : null;

    container.querySelectorAll('.ballot-item').forEach(function(item) {{
      var key = item.dataset.key;
      var count = votes[key] || 0;
      var isVoted = myVotes.indexOf(key) > -1;
      var isTop = key === topKey;
      var btn = item.querySelector('.ballot-vote-btn');
      item.querySelector('.ballot-vote-count').textContent = count;
      btn.classList.toggle('voted', isVoted);
      btn.querySelector('.ballot-arrow').innerHTML = isVoted ? '&#9733;' : '&#9650;';
      item.querySelector('.ballot-bar-fill').style.width = (count / maxV * 100) + '%';
      var tb = item.querySelector('.top-pick'); if (tb) tb.style.display = isTop ? 'inline-block' : 'none';
      var vb = item.querySelector('.voted-badge'); if (vb) vb.style.display = isVoted ? 'inline-block' : 'none';
      item.style.order = -count;
    }});

    var footer = document.getElementById('ballotFooter');
    if (footer) footer.textContent = 'Your votes: ' + myVotes.length + ' cast \u00B7 Click \u25B2 to vote \u00B7 Click again to unvote';
  }}

  container.addEventListener('click', function(e) {{
    var btn = e.target.closest('.ballot-vote-btn');
    if (!btn) return;
    var key = btn.dataset.key, votes = getVotes(), myVotes = getMyVotes();
    var idx = myVotes.indexOf(key);
    if (idx > -1) {{ myVotes.splice(idx, 1); votes[key] = Math.max(0, (votes[key] || 0) - 1); }}
    else {{ myVotes.push(key); votes[key] = (votes[key] || 0) + 1; }}
    save(votes, myVotes);
    btn.style.animation = 'pulse 0.3s ease';
    setTimeout(function(){{ btn.style.animation = ''; }}, 300);
    render();
  }});

  render();
}})();

// ── Post-Credits Feedback ──
(function() {{
  var fbKey = 'sr_feedback_' + SPRINT;
  var entries = document.getElementById('feedbackEntries');
  var nameInput = document.getElementById('feedbackName');
  var textInput = document.getElementById('feedbackText');
  var submitBtn = document.getElementById('feedbackSubmit');
  if (!entries || !submitBtn) return;

  var savedName = localStorage.getItem('sr_ticket_' + SPRINT);
  if (savedName && nameInput) nameInput.value = savedName;

  function getFeedback() {{ return lsGet(fbKey, []); }}

  function render() {{
    var items = getFeedback();
    if (!items.length) {{
      entries.innerHTML = '<div class="feedback-empty">No feedback yet &mdash; be the first to leave a note.</div>';
      return;
    }}
    entries.innerHTML = items.map(function(item) {{
      return '<div class="feedback-entry">' +
        '<div class="feedback-entry-header">' +
          '<span class="feedback-author">' + item.name + '</span>' +
          '<span class="feedback-time">' + item.time + '</span>' +
        '</div>' +
        '<div class="feedback-entry-text">' + item.text + '</div>' +
      '</div>';
    }}).join('');
  }}

  submitBtn.addEventListener('click', function() {{
    var name = nameInput.value.trim();
    var text = textInput.value.trim();
    if (!name || !text) return;
    var items = getFeedback();
    var now = new Date();
    var timeStr = now.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }}) + ' at ' +
                  now.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit' }});
    items.push({{ name: name, text: text.replace(/</g, '&lt;').replace(/>/g, '&gt;'), time: timeStr }});
    lsSet(fbKey, items);
    textInput.value = '';
    render();
  }});

  textInput.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submitBtn.click();
  }});

  render();
}})();
</script>

</body>
</html>'''

os.makedirs("output", exist_ok=True)
with open("output/sample_sprint_review.html", "w") as f:
    f.write(html)

print(f"Generated output/sample_sprint_review.html")
print(f"Sprint: {sprint['name']}")
print(f"Stories: {len(done_stories)}/{len(stories)} done, {points_completed:.0f}/{points_committed:.0f} points")
print(f"Sub-tasks: {len(done_subtasks)}/{len(subtasks)}")
print(f"Contributors: {len(contributor_stats)}")
print(f"Epics: {len(epic_map)}")
