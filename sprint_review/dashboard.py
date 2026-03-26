"""Generate self-contained HTML sprint review dashboards."""

import json
import random
from datetime import datetime
from . import config

STAKEHOLDERS = [
    "Jack Thompson", "Bill Martinez", "Gary Chen", "Jenna Park",
    "Sarah Williams", "Mike O'Brien", "Lisa Kumar", "Tom Nguyen",
    "Rachel Adams", "Derek Foster", "Amy Collins", "Bryce Barrand",
]

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


def generate(metrics, prev_filename=None, next_filename=None):
    """Generate a single sprint review HTML file. Returns the HTML string."""
    s = metrics
    sprint = s["sprint"]
    e = _esc
    base_url = s["base_url"]

    def issue_link(key, classes="text-secondary no-underline font-semibold hover:underline"):
        return f'<a href="{base_url}/browse/{key}" target="_blank" class="{classes}">{e(key)}</a>'

    # ── Chart data ──

    burndown_labels = json.dumps(list(s["burndown"].keys()))
    burndown_values = json.dumps(list(s["burndown"].values()))
    if s["burndown"]:
        ideal_step = s["points_committed"] / max(len(s["burndown"]) - 1, 1)
        ideal_values = json.dumps([round(s["points_committed"] - ideal_step * i, 1) for i in range(len(s["burndown"]))])
    else:
        ideal_values = "[]"

    vel_labels = json.dumps([v["name"].replace("FS02: ", "") for v in s["all_velocity"]])
    vel_committed = json.dumps([v["committed"] for v in s["all_velocity"]])
    vel_completed = json.dumps([v["completed"] for v in s["all_velocity"]])

    contrib_labels = json.dumps([name for name, _ in s["sorted_contributors"][:8]])
    contrib_points = json.dumps([round(st["points_share"], 1) for _, st in s["sorted_contributors"][:8]])
    contrib_subtasks = json.dumps([st["subtasks_done"] for _, st in s["sorted_contributors"][:8]])

    work_split_labels = json.dumps(["Defects / Bugs", "Planned Work"])
    work_split_values = json.dumps([s["bug_points"], s["planned_points"]])

    # ── Completed work HTML ──

    completed_html = ""
    story_idx = 0
    all_done_keys = [
        st["key"]
        for epic_stories in s["epic_map"].values()
        for st in epic_stories
        if st["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"
    ]
    demo_rng = random.Random(hash(sprint["name"]))
    demo_count = min(demo_rng.randint(3, 4), len(all_done_keys))
    demo_keys = set(demo_rng.sample(all_done_keys, demo_count))

    for epic_name, epic_stories in s["epic_map"].items():
        done_in_epic = [st for st in epic_stories if st["fields"].get("status", {}).get("statusCategory", {}).get("name") == "Done"]
        if not done_in_epic:
            continue

        epic_pts = sum((st["fields"].get(config.SP_FIELD) or 0) for st in done_in_epic)
        completed_html += f'''<div class="bg-surface-container rounded-2xl border border-white/5 overflow-hidden mb-4">
  <div class="p-6 flex items-center gap-6 border-b border-white/5">
    <span class="material-symbols-outlined text-primary text-2xl">theaters</span>
    <div>
      <h4 class="text-xl font-headline font-bold text-on-surface">{e(epic_name)}</h4>
      <span class="text-[11px] font-label uppercase text-on-surface-variant tracking-widest">{len(done_in_epic)} Stories &middot; {epic_pts:.0f} Points</span>
    </div>
  </div>
  <div class="divide-y divide-white/5">\n'''

        for story in done_in_epic:
            key = story["key"]
            summary = e(story["fields"].get("summary", ""))
            pts = story["fields"].get(config.SP_FIELD) or 0
            assignee = story["fields"].get("assignee")
            assignee_name = e(assignee.get("displayName", "Unassigned")) if assignee else "Unassigned"

            scope_badge = ""
            if s["scope_changes"].get(key) == "added_mid_sprint":
                scope_badge = ' <span class="px-2 py-0.5 bg-secondary/20 text-secondary text-[10px] font-label uppercase font-bold rounded-full border border-secondary/30 ml-2">Added mid-sprint</span>'

            desc = story["fields"].get("description")
            desc_text = _extract_description(desc)
            caption = _first_sentence(desc_text) or summary

            subs = s["parent_map"].get(key, [])
            subs_html = ""
            for sub in subs:
                sub_status = sub["fields"].get("status", {}).get("statusCategory", {}).get("name", "")
                sub_assignee = sub["fields"].get("assignee")
                sub_assignee_name = e(sub_assignee.get("displayName", "")) if sub_assignee else ""
                is_done = sub_status == "Done"
                icon = "check_circle" if is_done else "radio_button_unchecked"
                icon_color = "text-primary" if is_done else "text-on-surface-variant/40"
                text_color = "text-on-surface" if is_done else "text-on-surface-variant"
                subs_html += f'''      <div class="flex items-center gap-3 py-2 text-sm {text_color}">
        <span class="material-symbols-outlined {icon_color} text-lg">{icon}</span>
        {issue_link(sub["key"], "text-on-surface-variant no-underline hover:text-secondary text-sm")} <span class="flex-1">{e(sub["fields"].get("summary", ""))}</span>
        <span class="text-on-surface-variant text-xs">{sub_assignee_name}</span>
      </div>\n'''

            sub_count = len(subs)

            demo_html = ""
            if key in demo_keys:
                gif_url = DEMO_GIFS[story_idx % len(DEMO_GIFS)]
                demo_html = f'''    <div class="border-t border-white/5 bg-black/20">
      <p class="px-6 pt-4 text-on-surface-variant text-sm italic">{e(caption)}</p>
      <img src="{gif_url}" alt="Feature demo for {e(key)}" class="w-full max-h-80 object-cover mt-3" loading="lazy">
    </div>\n'''

            completed_html += f'''    <div class="story-card" data-story-key="{e(key)}">
      <div class="px-6 py-4 flex items-center gap-4">
        <button class="feature-star-btn" data-key="{e(key)}" title="Pick as your favorite feature">
          <span class="material-symbols-outlined text-on-surface-variant hover:text-secondary transition-colors text-xl cursor-pointer">star</span>
        </button>
        <span class="story-key">{issue_link(key)}</span>
        <span class="story-summary flex-1 font-medium text-on-surface">{summary}{scope_badge}</span>
        <span class="text-on-surface-variant text-sm">{pts:.0f} pts &middot; {assignee_name}</span>
      </div>
{demo_html}      <details>
        <summary class="subtask-toggle px-6 py-3 text-sm text-on-surface-variant cursor-pointer border-t border-white/5 hover:text-secondary transition-colors font-label uppercase tracking-widest text-[11px] font-bold list-none">
          View {sub_count} subtask{"s" if sub_count != 1 else ""}
        </summary>
        <div class="px-6 pb-4">
{subs_html}        </div>
      </details>
    </div>\n'''
            story_idx += 1

        completed_html += "  </div>\n</div>\n"

    # ── Carry-over HTML ──

    carryover_rows = ""
    for item in s["carryover"]:
        scope_badge = ""
        if s["scope_changes"].get(item["key"]) == "added_mid_sprint":
            scope_badge = ' <span class="px-2 py-0.5 bg-secondary/20 text-secondary text-[10px] font-label uppercase font-bold rounded-full border border-secondary/30 ml-2">Added mid-sprint</span>'
        carryover_rows += f'''<tr class="hover:bg-white/[0.03] transition-colors">
  <td class="px-8 py-4">{issue_link(item["key"])}</td>
  <td class="px-8 py-4">{e(item["summary"])}{scope_badge}</td>
  <td class="px-8 py-4"><span class="px-3 py-1 bg-primary/10 text-primary text-[11px] rounded-full uppercase font-bold">{e(item["status"])}</span></td>
  <td class="px-8 py-4">{item["points"]:.0f}</td>
  <td class="px-8 py-4">{e(item["assignee"])}</td>
</tr>\n'''

    if not carryover_rows:
        carryover_rows = '<tr><td colspan="5" class="px-8 py-8 text-center text-on-surface-variant italic">Nothing left behind. Clean sweep!</td></tr>'

    # ── Coming Attractions Ballot HTML ──

    ballot_html = ""
    if s["next_sprint"] and s["next_sprint"]["id"] != sprint["id"]:
        ns = s["next_sprint"]
        ballot_html += f'''<section class="space-y-12">
  <div class="flex justify-between items-end border-b border-white/10 pb-6">
    <h3 class="font-headline font-black text-5xl text-on-surface tracking-tight uppercase">Coming Attractions</h3>
    <span class="font-label text-[11px] uppercase tracking-[0.3em] text-on-surface-variant font-bold">{e(ns["name"])}</span>
  </div>\n'''
        if ns.get("goal"):
            ballot_html += f'  <p class="text-on-surface-variant"><strong class="text-on-surface">Sprint Goal:</strong> {e(ns["goal"])}</p>\n'
        ballot_html += '  <div class="space-y-4" id="ballotContainer">\n'
        for ni in s["coming_next"][:10]:
            ni_key = ni["key"]
            ballot_html += f'''    <div class="ballot-item bg-surface-container px-8 py-6 rounded-2xl border border-white/5 flex items-center gap-8 hover:border-primary/40 transition-all" data-key="{e(ni_key)}" id="ballot-{e(ni_key)}">
      <button class="ballot-vote-btn flex flex-col items-center gap-1 p-3 rounded-xl bg-black/40 border border-white/5 hover:bg-primary/10 transition-colors cursor-pointer" data-key="{e(ni_key)}">
        <span class="ballot-arrow material-symbols-outlined text-on-surface-variant text-3xl">arrow_drop_up</span>
        <span class="ballot-vote-count text-sm font-label font-black text-on-surface" id="count-{e(ni_key)}">0</span>
      </button>
      <div class="flex-1 space-y-2">
        <div class="ballot-title flex items-center gap-3">
          {issue_link(ni_key)} <span class="font-medium">&middot; {e(ni["summary"])}</span>
          <span class="ballot-badge top-pick px-2 py-0.5 bg-secondary/20 text-secondary text-[10px] font-label uppercase font-bold rounded-full border border-secondary/20" id="badge-{e(ni_key)}" style="display:none">top pick</span>
          <span class="ballot-badge voted-badge px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] font-label uppercase font-bold rounded-full border border-emerald-500/20" id="voted-{e(ni_key)}" style="display:none">voted</span>
        </div>
        <div class="ballot-meta text-sm text-on-surface-variant">{ni["points"] or "-"} pts &middot; {e(ni["assignee"])}</div>
        <div class="h-1.5 bg-black rounded-full overflow-hidden border border-white/5">
          <div class="ballot-bar-fill h-full bg-primary rounded-full transition-all duration-500" id="bar-{e(ni_key)}" style="width:0%"></div>
        </div>
      </div>
    </div>\n'''
        ballot_html += '  </div>\n'
        ballot_html += '  <div class="ballot-footer text-center py-4 text-sm text-on-surface-variant font-label" id="ballotFooter">Click &#9650; to vote &middot; Click again to unvote</div>\n'
        ballot_html += '</section>\n'
    elif not s["next_sprint"]:
        ballot_html = '<section class="space-y-12"><h3 class="font-headline font-black text-5xl text-on-surface tracking-tight uppercase">Coming Attractions</h3><p class="text-on-surface-variant italic">No upcoming sprints scheduled.</p></section>\n'

    # ── Contributors table rows ──

    contrib_rows = ""
    for name, stats in s["sorted_contributors"][:10]:
        highlight = ""
        badge_html = ""
        if stats["subtasks_done"] > 0 and name != "Unassigned":
            if s["mvp"] and name == s["mvp"][0]:
                highlight = "MVP"
                badge_html = '<span class="px-3 py-1 bg-secondary/10 text-secondary text-[11px] rounded-full uppercase font-black">MVP</span>'
            elif s["workhorse"] and name == s["workhorse"][0]:
                highlight = "Workhorse"
                badge_html = '<span class="px-3 py-1 bg-secondary/10 text-secondary text-[11px] rounded-full uppercase font-black">WORKHORSE</span>'
            elif s["speed_demon"] and name == s["speed_demon"][0]:
                highlight = "Speed Demon"
                badge_html = '<span class="px-3 py-1 bg-primary/10 text-primary text-[11px] rounded-full uppercase font-black">SPEED</span>'

        initials = "".join(w[0] for w in name.split()[:2]).upper()
        contrib_rows += f'''<tr class="hover:bg-white/[0.03] transition-colors" data-member="{e(name)}">
  <td class="px-8 py-5 flex items-center gap-4">
    <div class="w-10 h-10 rounded-full bg-surface-container border border-white/10 flex items-center justify-center text-sm font-bold text-secondary">{initials}</div>
    <span class="text-on-surface font-bold">{e(name)}</span>
  </td>
  <td class="px-8 py-5 text-primary font-black">{stats["points_share"]:.1f}</td>
  <td class="px-8 py-5">{stats["subtasks_done"]}</td>
  <td class="px-8 py-5">{stats["stories_owned"]}</td>
  <td class="px-8 py-5">{badge_html}</td>
  <td class="px-8 py-5 text-right">
    <button class="cast-vote-btn text-primary hover:text-secondary transition-colors transform active:scale-90 cursor-pointer" data-member="{e(name)}">
      <span class="material-symbols-outlined text-2xl">back_hand</span>
    </button>
  </td>
</tr>\n'''

    # ── Awards HTML ──

    awards_html = _build_awards_html(s, s.get("sprint_index", 0))

    # ── Preseeded attendance ──

    rng = random.Random(hash(sprint["name"]))
    n = rng.randint(6, 9)
    preseeded_attendees = rng.sample(STAKEHOLDERS, n)
    if "Bryce Barrand" not in preseeded_attendees:
        preseeded_attendees[-1] = "Bryce Barrand"

    preseed_feature_key = s["done_stories"][0]["key"] if s["done_stories"] else ""
    preseed_cast_member = s["sorted_contributors"][0][0] if s["sorted_contributors"] else ""

    stakeholders_json = json.dumps(STAKEHOLDERS)
    preseeded_json = json.dumps(preseeded_attendees)

    # ── Nav links ──

    prev_link = f'<a href="{prev_filename}" class="text-primary font-bold font-label uppercase text-sm tracking-widest hover:text-secondary transition-colors">&larr; Previous</a>' if prev_filename else '<span class="text-on-surface-variant/40 font-label uppercase text-sm tracking-widest">&larr; Previous</span>'
    next_link = f'<a href="{next_filename}" class="text-primary font-bold font-label uppercase text-sm tracking-widest hover:text-secondary transition-colors">Next &rarr;</a>' if next_filename else '<span class="text-on-surface-variant/40 font-label uppercase text-sm tracking-widest">Next &rarr;</span>'

    # ── Assemble page ──

    completion_rate = s["completion_rate"]
    goal_met = s["goal_met"]
    goal_color_class = "text-emerald-400" if goal_met else "text-primary"
    goal_bg_class = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" if goal_met else "bg-primary/10 text-primary border-primary/30"
    grade_text_class = "text-secondary"
    progress_bar_color = "#4ecca3" if goal_met else "#D32F2F"
    vel_delta_html = f' &middot; <span class="text-error font-bold">{e(s["vel_delta"])}</span>' if s["vel_delta"] else ""

    html = f'''<!DOCTYPE html>
<html class="dark" lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sprint Review: {e(sprint["name"])}</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400..800&family=Space+Grotesk:wght@300..700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script>
tailwind.config = {{
  darkMode: "class",
  theme: {{
    extend: {{
      colors: {{
        "primary": "#D32F2F",
        "on-primary": "#ffffff",
        "primary-container": "#9a1c1c",
        "secondary": "#FFD700",
        "on-secondary": "#000000",
        "surface": "#0a0a0a",
        "surface-container": "#171717",
        "surface-container-high": "#262626",
        "on-surface": "#f5f5f5",
        "on-surface-variant": "#a3a3a3",
        "outline": "#404040",
        "error": "#ef4444"
      }},
      fontFamily: {{
        "headline": ["Newsreader", "serif"],
        "body": ["Space Grotesk", "sans-serif"],
        "label": ["Space Grotesk", "sans-serif"]
      }},
    }},
  }},
}}
</script>
<style>
.material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
.spotlight-glow {{ background: radial-gradient(circle at 50% 0%, rgba(211, 47, 47, 0.1) 0%, transparent 70%); }}
.ticket-edge {{
  mask-image: radial-gradient(circle at 0 50%, transparent 12px, black 13px), radial-gradient(circle at 100% 50%, transparent 12px, black 13px);
  mask-composite: intersect;
}}
::-webkit-scrollbar {{ width: 8px; }}
::-webkit-scrollbar-track {{ background: #0a0a0a; }}
::-webkit-scrollbar-thumb {{ background: #262626; border-radius: 10px; }}
::-webkit-scrollbar-thumb:hover {{ background: #D32F2F; }}
.feature-star-btn.selected span {{ font-variation-settings: 'FILL' 1; color: #FFD700; }}
.cast-vote-btn.selected {{ color: #FFD700 !important; }}
.cast-vote-btn.selected span {{ font-variation-settings: 'FILL' 1; }}
.feature-fav-banner, .cast-fav-banner {{ display: none; }}
.feature-fav-banner.visible, .cast-fav-banner.visible {{ display: block; animation: fadeInUp 0.3s ease; }}
.ticket-stub.locked {{ opacity: 0.5; pointer-events: none; }}
.ticket-stub.locked.allow-progress {{ pointer-events: auto; }}
.ticket-step.done {{ color: #4ecca3; }}
.ticket-step.done .step-icon {{ border-color: #4ecca3; background: #4ecca3; color: #0a0a0a; }}
.ticket-avatar.pending {{ opacity: 0.3; }}
.ticket-avatar.pending .ticket-initials {{ border-style: dashed; background: transparent; color: #a3a3a3; border-color: #a3a3a3; }}
.ticket-checkin.tear-away {{ animation: tearAway 0.4s ease forwards; }}
.ballot-vote-btn.voted {{ border-color: #FFD700 !important; background: #FFD700 !important; }}
.ballot-vote-btn.voted .ballot-arrow {{ color: #0a0a0a !important; }}
.ballot-vote-btn.voted .ballot-vote-count {{ color: #0a0a0a !important; }}
details > summary {{ list-style: none; }}
details > summary::-webkit-details-marker {{ display: none; }}
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
<body class="bg-surface text-on-surface font-body selection:bg-primary/40">

<header class="fixed top-0 w-full z-50 bg-black/80 backdrop-blur-xl border-b border-white/10 shadow-2xl flex justify-between items-center px-8 h-16">
  <div class="flex items-center gap-8">
    {prev_link}
  </div>
  <a href="index.html" class="text-xl font-black text-on-surface uppercase tracking-tighter font-headline hover:text-secondary transition-colors">Now Showing</a>
  <div class="flex items-center gap-8">
    {next_link}
  </div>
</header>

<main class="pt-28 pb-32 px-6 max-w-7xl mx-auto space-y-28">

<!-- Hero Section -->
<section class="relative overflow-hidden rounded-[2rem] bg-surface-container p-12 lg:p-20 spotlight-glow border border-white/5">
  <div class="absolute top-0 right-0 p-12 opacity-[0.03]">
    <span class="material-symbols-outlined text-[15rem]">movie</span>
  </div>
  <div class="relative z-10 grid lg:grid-cols-2 gap-16 items-center">
    <div class="space-y-8">
      <div class="inline-block px-5 py-1.5 border border-primary/40 rounded-full text-primary font-label text-xs tracking-[0.2em] uppercase font-bold">
        {e(config.TEAM_NAME)}
      </div>
      <h1 class="text-7xl lg:text-9xl font-headline font-black text-on-surface tracking-tighter leading-[0.85]">
        {e(sprint["name"].split(":")[0])}:<br><span class="text-primary">{e(sprint["name"].split(":")[-1].strip())}</span>
      </h1>
      <div class="flex items-center gap-4 py-4 border-y border-white/10">
        <p class="font-label text-sm uppercase tracking-widest text-on-surface-variant font-medium">
          {s["sprint_date_range"]} &middot; Starring: {e(", ".join(s["cast_list"][:6]))}
        </p>
      </div>
    </div>

    <!-- Goal Card -->
    <div class="bg-surface-container-high p-8 rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.5)] border border-white/5 relative overflow-hidden">
      <div class="absolute -top-10 -right-10 w-40 h-40 bg-primary/10 rounded-full blur-3xl"></div>
      <div class="flex justify-between items-start mb-8">
        <div class="flex-1 mr-6">
          <span class="text-primary font-label text-xs tracking-widest uppercase font-bold block mb-2">Sprint Goal</span>
          <blockquote class="text-xl font-headline text-on-surface leading-tight font-medium">
            &ldquo;{e(s["goal_text"])}&rdquo;
          </blockquote>
        </div>
        <div class="text-right flex-shrink-0">
          <div class="text-6xl font-headline font-black {grade_text_class}">{s["grade"]}</div>
          <div class="text-[10px] font-label uppercase tracking-widest text-on-surface-variant">{e(s["grade_label"])}</div>
        </div>
      </div>
      <p class="text-on-surface-variant text-sm mb-6">Completed {len(s["done_stories"])} of {len(s["stories"])} stories. {len(s["carryover"])} carried over.</p>
      <div class="space-y-4">
        <div class="flex justify-between items-end">
          <span class="font-label text-xs uppercase text-on-surface-variant font-medium">Progress ({len(s["done_stories"])}/{len(s["stories"])} Stories)</span>
          <span class="font-label text-lg font-black text-primary">{completion_rate:.0f}%</span>
        </div>
        <div class="h-3 bg-black rounded-full overflow-hidden border border-white/5">
          <div class="h-full rounded-full shadow-[0_0_15px_rgba(211,47,47,0.6)]" style="width:{completion_rate:.0f}%;background:{progress_bar_color}"></div>
        </div>
        <div class="flex justify-between pt-4 border-t border-white/5 font-label text-xs uppercase tracking-widest text-on-surface-variant">
          <span>{s["points_completed"]:.0f} of {s["points_committed"]:.0f} points</span>
          {vel_delta_html}
        </div>
      </div>
      <div class="mt-8">
        <div class="w-full py-3 {goal_bg_class} border font-label text-sm font-black text-center rounded-lg tracking-[0.3em] uppercase">
          {"Goal Achieved" if goal_met else "Goal Not Met"}
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Narrative Trailer -->
<section class="max-w-4xl mx-auto text-center space-y-8">
  <h2 class="font-label text-sm uppercase tracking-[0.5em] text-primary font-bold">The Trailer</h2>
  <p class="text-2xl lg:text-3xl font-headline leading-tight text-on-surface/90">{s["narrative"]}</p>
</section>

<!-- Box Office Numbers -->
<section class="space-y-10">
  <div class="flex items-center gap-6">
    <h3 class="font-label text-xs uppercase tracking-[0.4em] text-on-surface-variant font-bold whitespace-nowrap">Box Office Earnings</h3>
    <div class="h-px w-full bg-white/10"></div>
  </div>
  <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6">
    <div class="bg-surface-container p-6 rounded-xl border border-white/5 hover:border-primary/30 transition-colors">
      <div class="text-[11px] font-label uppercase tracking-widest text-on-surface-variant mb-2 font-bold">Stories</div>
      <div class="text-3xl font-headline font-black text-on-surface">{len(s["done_stories"])} <span class="text-sm opacity-20 font-sans">/ {len(s["stories"])}</span></div>
    </div>
    <div class="bg-surface-container p-6 rounded-xl border border-white/5 hover:border-secondary/30 transition-colors">
      <div class="text-[11px] font-label uppercase tracking-widest text-on-surface-variant mb-2 font-bold">Points</div>
      <div class="text-3xl font-headline font-black text-on-surface">{s["points_completed"]:.0f} <span class="text-sm opacity-20 font-sans">/ {s["points_committed"]:.0f}</span></div>
    </div>
    <div class="bg-surface-container p-6 rounded-xl border border-white/5 hover:border-primary/30 transition-colors">
      <div class="text-[11px] font-label uppercase tracking-widest text-on-surface-variant mb-2 font-bold">Completion</div>
      <div class="text-3xl font-headline font-black text-on-surface">{completion_rate:.0f}%</div>
    </div>
    <div class="bg-surface-container p-6 rounded-xl border border-white/5 hover:border-secondary/30 transition-colors">
      <div class="text-[11px] font-label uppercase tracking-widest text-on-surface-variant mb-2 font-bold">Sub-tasks</div>
      <div class="text-3xl font-headline font-black text-on-surface">{len(s["done_subtasks"])} <span class="text-sm opacity-20 font-sans">/ {len(s["subtasks"])}</span></div>
    </div>
    <div class="bg-surface-container p-6 rounded-xl border border-white/5 hover:border-primary/30 transition-colors">
      <div class="text-[11px] font-label uppercase tracking-widest text-on-surface-variant mb-2 font-bold">Cycle Time</div>
      <div class="text-3xl font-headline font-black text-on-surface">{s["avg_cycle_time"]:.1f}<span class="text-lg opacity-40">d</span></div>
    </div>
    <div class="bg-surface-container p-6 rounded-xl border-2 border-primary/20">
      <div class="text-[11px] font-label uppercase tracking-widest text-on-surface-variant mb-2 font-bold">Carry Over</div>
      <div class="text-3xl font-headline font-black text-error">{len(s["carryover"])}</div>
    </div>
  </div>
</section>

<!-- Academy Awards -->
{awards_html}

<!-- Behind the Scenes: Charts -->
<section class="space-y-10">
  <h3 class="font-label text-xs uppercase tracking-[0.5em] text-on-surface-variant font-bold">Behind the Scenes: Analytics</h3>
  <div class="grid lg:grid-cols-2 gap-8">
    <div class="bg-surface-container p-8 rounded-2xl border border-white/5 relative">
      <span class="font-label text-xs uppercase tracking-widest text-on-surface-variant block mb-6 font-bold">Burndown Curve</span>
      <div style="position:relative; height:220px;"><canvas id="burndownChart"></canvas></div>
    </div>
    <div class="bg-surface-container p-8 rounded-2xl border border-white/5 relative">
      <span class="font-label text-xs uppercase tracking-widest text-on-surface-variant block mb-6 font-bold">Velocity Trend</span>
      <div style="position:relative; height:220px;"><canvas id="velocityChart"></canvas></div>
    </div>
    <div class="bg-surface-container p-8 rounded-2xl border border-white/5 relative">
      <span class="font-label text-xs uppercase tracking-widest text-on-surface-variant block mb-6 font-bold">Contributor Share</span>
      <div style="position:relative; height:220px;"><canvas id="contribChart"></canvas></div>
    </div>
    <div class="bg-surface-container p-8 rounded-2xl border border-white/5 relative">
      <span class="font-label text-xs uppercase tracking-widest text-on-surface-variant block mb-6 font-bold">Bugs vs Planned Work</span>
      <div style="position:relative; height:220px;"><canvas id="workSplitChart"></canvas></div>
    </div>
  </div>
</section>

<!-- It's a Wrap: Completed Work -->
<section class="space-y-10">
  <h3 class="font-headline font-black text-5xl text-on-surface tracking-tight uppercase">It&rsquo;s a Wrap</h3>
  <p class="text-on-surface-variant text-sm"><span class="material-symbols-outlined text-secondary text-base align-middle">star</span> Click the star on your favorite feature release</p>
  <div class="feature-fav-banner bg-secondary/5 border border-secondary/30 rounded-xl px-6 py-4 text-center text-secondary font-label" id="featureFavBanner"></div>
  {completed_html}
</section>

<!-- The Cast: Team Contributions -->
<section class="space-y-10">
  <h3 class="font-label text-xs uppercase tracking-[0.5em] text-on-surface-variant font-bold">The Cast Performance</h3>
  <p class="text-on-surface-variant text-sm"><span class="material-symbols-outlined text-primary text-base align-middle">back_hand</span> Give a High 5 to the team member who earned it this sprint</p>
  <div class="cast-fav-banner bg-secondary/5 border border-secondary/30 rounded-xl px-6 py-4 text-center text-secondary font-label" id="castFavBanner"></div>
  <div class="bg-surface-container-high rounded-3xl overflow-hidden border border-white/5">
    <table class="w-full text-left font-label" id="castTable">
      <thead class="bg-black/40 text-[11px] uppercase tracking-widest text-on-surface-variant border-b border-white/5">
        <tr><th class="px-8 py-5">Contributor</th><th class="px-8 py-5">Points</th><th class="px-8 py-5">Sub-tasks</th><th class="px-8 py-5">Stories</th><th class="px-8 py-5">Award</th><th class="px-8 py-5 text-right">High 5</th></tr>
      </thead>
      <tbody class="divide-y divide-white/5">{contrib_rows}</tbody>
    </table>
  </div>
</section>

<!-- Carry-Over -->
<section class="space-y-10">
  <div class="flex items-center gap-6">
    <h3 class="font-label text-xs uppercase tracking-[0.4em] text-on-surface-variant font-bold whitespace-nowrap">Left on the Cutting Room Floor</h3>
    <div class="h-px w-full bg-white/10"></div>
  </div>
  <div class="bg-surface-container-high rounded-3xl overflow-hidden border border-white/5">
    <table class="w-full text-left font-label">
      <thead class="bg-black/40 text-[11px] uppercase tracking-widest text-on-surface-variant border-b border-white/5">
        <tr><th class="px-8 py-5">Issue</th><th class="px-8 py-5">Summary</th><th class="px-8 py-5">Status</th><th class="px-8 py-5">Points</th><th class="px-8 py-5">Assignee</th></tr>
      </thead>
      <tbody class="divide-y divide-white/5">{carryover_rows}</tbody>
    </table>
  </div>
</section>

<!-- Coming Attractions Ballot -->
{ballot_html}

<!-- Ticket Stub -->
<section class="flex justify-center py-8">
  <div class="ticket-stub w-full max-w-lg bg-on-surface text-surface p-10 rounded-2xl ticket-edge shadow-2xl space-y-8 relative overflow-hidden" id="ticketStub" data-sprint="{e(sprint["name"])}">
    <div class="absolute top-0 left-0 w-full h-2.5 bg-primary"></div>
    <div class="text-center space-y-2">
      <span class="font-label text-xs uppercase tracking-[0.4em] font-black text-surface/50">Ticket Stub</span>
      <h3 class="font-headline font-black text-3xl uppercase tracking-tight">Check-in for Premiere</h3>
    </div>
    <div class="ticket-progress" id="ticketProgress">
      <div class="text-center text-xs uppercase tracking-widest text-surface/50 font-bold mb-4">Complete these steps to check in</div>
      <div class="flex gap-6 justify-center">
        <div class="ticket-step flex items-center gap-2 text-sm text-surface/50" id="stepFeature">
          <span class="step-icon w-6 h-6 rounded-full border-2 border-surface/20 flex items-center justify-center text-xs">1</span> Pick a favorite feature
        </div>
        <div class="ticket-step flex items-center gap-2 text-sm text-surface/50" id="stepCast">
          <span class="step-icon w-6 h-6 rounded-full border-2 border-surface/20 flex items-center justify-center text-xs">2</span> High-5 a team member
        </div>
      </div>
    </div>
    <div class="ticket-checkin space-y-4" id="ticketCheckin" style="display:none;">
      <input class="w-full bg-black/5 border-dashed border-2 border-black/20 rounded-xl py-4 px-6 text-center font-headline text-xl focus:ring-0 focus:border-primary transition-all placeholder:text-black/30" id="ticketName" placeholder="Enter your name..." type="text">
      <button class="w-full py-4 bg-primary text-white font-label uppercase font-black tracking-widest text-sm hover:bg-black transition-colors rounded-xl shadow-lg cursor-pointer" id="ticketTear">Tear Ticket</button>
    </div>
    <div class="hidden text-center py-8 border-2 border-dashed border-primary rounded-xl bg-primary/5 space-y-4" id="ticketConfirmed" style="display:none;">
      <span class="material-symbols-outlined text-primary text-4xl block">verified</span>
      <p class="font-headline font-black text-xl">You&rsquo;re checked in, <strong id="ticketWho"></strong></p>
      <div class="flex flex-col gap-2 text-sm text-surface/60 pt-2" id="ticketVoteSummary"></div>
    </div>
    <div class="ticket-attendance text-center">
      <div class="text-sm text-surface/50 mb-4"><span id="attendeeCount">0</span> attended this screening</div>
      <div class="flex flex-wrap gap-3 justify-center" id="ticketAvatars"></div>
    </div>
  </div>
</section>

<!-- Post-Credits Feedback -->
<section class="max-w-3xl mx-auto space-y-10">
  <h3 class="font-label text-xs uppercase tracking-[0.5em] text-center text-on-surface-variant font-bold">Post-Credits Feedback</h3>
  <div class="bg-surface-container p-8 rounded-3xl space-y-8 border border-white/5" id="feedbackBox">
    <p class="text-on-surface-variant text-sm text-center">Got a question about something that shipped? Feedback on a feature? Drop it here.</p>
    <div class="space-y-4 max-h-96 overflow-y-auto" id="feedbackEntries"></div>
    <div class="space-y-3" id="feedbackForm">
      <input type="text" id="feedbackName" placeholder="Your name" class="w-full bg-black/40 border border-white/10 focus:ring-2 focus:ring-primary/50 focus:border-primary text-on-surface rounded-xl px-5 py-3 font-label text-sm">
      <textarea id="feedbackText" placeholder="Write your question or feedback..." rows="3" class="w-full bg-black/40 border border-white/10 focus:ring-2 focus:ring-primary/50 focus:border-primary text-on-surface rounded-xl px-5 py-3 font-label text-sm resize-vertical"></textarea>
      <div class="flex justify-end">
        <button id="feedbackSubmit" class="px-6 py-3 bg-primary text-white rounded-xl hover:bg-secondary hover:text-black transition-all transform active:scale-95 shadow-lg font-label font-bold text-sm cursor-pointer">
          <span class="material-symbols-outlined text-lg align-middle mr-1">send</span> Submit
        </button>
      </div>
    </div>
  </div>
</section>

</main>

<footer class="text-center py-12 text-on-surface-variant text-sm border-t border-white/5">
  Generated automatically by Sprint Review Automation &middot; {datetime.now().strftime("%B %d, %Y")}
</footer>

<script>
function initCharts() {{
  var RED = '#D32F2F', GOLD = '#FFD700', TEXT = '#f5f5f5', GRID = 'rgba(255,255,255,0.05)';

  new Chart(document.getElementById('burndownChart').getContext('2d'), {{
    type: 'line',
    data: {{
      labels: {burndown_labels},
      datasets: [
        {{ label: 'Planned', data: {ideal_values}, borderColor: 'rgba(255,255,255,0.2)', borderDash: [5,5], pointRadius: 0, tension: 0, fill: false }},
        {{ label: 'Actual', data: {burndown_values}, borderColor: RED, backgroundColor: 'rgba(211,47,47,0.1)', fill: true, tension: 0.4, pointRadius: 3, pointBackgroundColor: RED }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ grid: {{ color: GRID }}, ticks: {{ color: TEXT }}, beginAtZero: true }},
        x: {{ grid: {{ display: false }}, ticks: {{ color: TEXT, maxTicksLimit: 10 }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('velocityChart').getContext('2d'), {{
    type: 'bar',
    data: {{
      labels: {vel_labels},
      datasets: [
        {{ label: 'Committed', data: {vel_committed}, backgroundColor: 'rgba(211,47,47,0.3)', borderRadius: 8 }},
        {{ label: 'Completed', data: {vel_completed}, backgroundColor: RED, borderRadius: 8 }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ color: TEXT, font: {{ family: 'Space Grotesk', size: 12 }} }} }} }},
      scales: {{
        y: {{ grid: {{ color: GRID }}, ticks: {{ color: TEXT }}, beginAtZero: true }},
        x: {{ grid: {{ display: false }}, ticks: {{ color: TEXT }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('contribChart').getContext('2d'), {{
    type: 'bar',
    data: {{
      labels: {contrib_labels},
      datasets: [
        {{ label: 'Points', data: {contrib_points}, backgroundColor: GOLD, borderRadius: 4 }},
        {{ label: 'Sub-tasks', data: {contrib_subtasks}, backgroundColor: 'rgba(255,215,0,0.3)', borderRadius: 4 }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {{ legend: {{ position: 'bottom', labels: {{ color: TEXT, font: {{ family: 'Space Grotesk', size: 12 }} }} }} }},
      scales: {{
        x: {{ grid: {{ color: GRID }}, ticks: {{ color: TEXT }} }},
        y: {{ grid: {{ display: false }}, ticks: {{ color: TEXT }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('workSplitChart').getContext('2d'), {{
    type: 'doughnut',
    data: {{
      labels: {work_split_labels},
      datasets: [{{ data: {work_split_values}, backgroundColor: [RED, '#4ecca3'], borderWidth: 0 }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      cutout: '75%',
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ color: TEXT, font: {{ family: 'Space Grotesk', size: 12 }} }} }},
        tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.label + ': ' + ctx.parsed + ' pts'; }} }} }}
      }}
    }}
  }});
}}

window.onload = function() {{
  try {{ initCharts(); }} catch(e) {{ console.error('Chart init failed:', e); }}
  try {{ initInteractive(); }} catch(e) {{ console.error('Interactive init failed:', e); }}
}};

function initInteractive() {{
// ── Shared State ──
var SPRINT = document.getElementById('ticketStub').dataset.sprint;
var STAKEHOLDERS = {stakeholders_json};
var PRESEEDED = {preseeded_json};
var CURRENT_USER = 'Bryce Barrand';
function lsGet(k, fb) {{ try {{ return JSON.parse(localStorage.getItem(k)) || fb; }} catch(e) {{ return fb; }} }}
function lsSet(k, v) {{ localStorage.setItem(k, JSON.stringify(v)); }}

(function() {{
  var seedKey = 'sr_seeded3_' + SPRINT;
  if (!localStorage.getItem(seedKey)) {{
    lsSet('sr_attendees_' + SPRINT, PRESEEDED);
    localStorage.setItem('sr_ticket_' + SPRINT, CURRENT_USER);
    if ('{preseed_feature_key}') localStorage.setItem('sr_fav_feature_' + SPRINT, '{preseed_feature_key}');
    if ('{preseed_cast_member}') localStorage.setItem('sr_fav_cast_' + SPRINT, '{preseed_cast_member}');
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
      btn.classList.toggle('selected', btn.dataset.key === fav);
    }});
    var banner = document.getElementById('featureFavBanner');
    if (banner && fav) {{
      var card = document.querySelector('.story-card[data-story-key="' + fav + '"]');
      var title = card ? card.querySelector('.story-summary').textContent.trim() : fav;
      banner.innerHTML = '<span class="material-symbols-outlined align-middle" style="font-variation-settings:\\x27FILL\\x27 1">star</span> Your Audience Choice: <strong>' + title + '</strong>';
      banner.classList.add('visible');
    }} else if (banner) {{ banner.classList.remove('visible'); }}
    updateTicketGate();
  }}
  document.addEventListener('click', function(e) {{
    var btn = e.target.closest('.feature-star-btn');
    if (!btn) return;
    e.preventDefault(); e.stopPropagation();
    var current = localStorage.getItem(fKey);
    if (current === btn.dataset.key) localStorage.removeItem(fKey);
    else localStorage.setItem(fKey, btn.dataset.key);
    render();
  }});
  render();
}})();

// ── Cast High-5 Vote ──
(function() {{
  var cKey = 'sr_fav_cast_' + SPRINT;
  var table = document.getElementById('castTable');
  if (!table) return;
  function render() {{
    var fav = localStorage.getItem(cKey);
    table.querySelectorAll('.cast-vote-btn').forEach(function(btn) {{
      btn.classList.toggle('selected', btn.dataset.member === fav);
    }});
    var banner = document.getElementById('castFavBanner');
    if (banner && fav) {{
      banner.innerHTML = '<span class="material-symbols-outlined align-middle" style="font-variation-settings:\\x27FILL\\x27 1">back_hand</span> Fan Favorite: <strong>' + fav + '</strong>';
      banner.classList.add('visible');
    }} else if (banner) {{ banner.classList.remove('visible'); }}
    updateTicketGate();
  }}
  table.addEventListener('click', function(e) {{
    var btn = e.target.closest('.cast-vote-btn');
    if (!btn) return;
    var current = localStorage.getItem(cKey);
    if (current === btn.dataset.member) localStorage.removeItem(cKey);
    else localStorage.setItem(cKey, btn.dataset.member);
    render();
  }});
  render();
}})();

// ── Ticket Stub ──
function renderVoteSummary() {{
  var el = document.getElementById('ticketVoteSummary');
  if (!el) return;
  var lines = [];
  var featKey = localStorage.getItem('sr_fav_feature_' + SPRINT);
  if (featKey) {{
    var card = document.querySelector('.story-card[data-story-key="' + featKey + '"]');
    var title = card ? card.querySelector('.story-summary').textContent.trim() : featKey;
    lines.push('<span class="material-symbols-outlined text-secondary text-base align-middle" style="font-variation-settings:\\x27FILL\\x27 1">star</span> Best Feature: <strong>' + title + '</strong>');
  }}
  var castName = localStorage.getItem('sr_fav_cast_' + SPRINT);
  if (castName) {{
    lines.push('<span class="material-symbols-outlined text-secondary text-base align-middle" style="font-variation-settings:\\x27FILL\\x27 1">back_hand</span> Top Performer: <strong>' + castName + '</strong>');
  }}
  el.innerHTML = lines.join('');
}}

function updateTicketGate() {{
  var stub = document.getElementById('ticketStub');
  if (!stub) return;
  var hasFeat = !!localStorage.getItem('sr_fav_feature_' + SPRINT);
  var hasCast = !!localStorage.getItem('sr_fav_cast_' + SPRINT);
  var isCheckedIn = !!localStorage.getItem('sr_ticket_' + SPRINT);
  var sf = document.getElementById('stepFeature'), sc = document.getElementById('stepCast');
  if (sf) {{ sf.classList.toggle('done', hasFeat); sf.querySelector('.step-icon').innerHTML = hasFeat ? '&#10003;' : '1'; }}
  if (sc) {{ sc.classList.toggle('done', hasCast); sc.querySelector('.step-icon').innerHTML = hasCast ? '&#10003;' : '2'; }}
  var unlocked = hasFeat && hasCast;
  stub.classList.toggle('locked', !unlocked && !isCheckedIn);
  if (isCheckedIn) {{
    document.getElementById('ticketProgress').style.display = 'none';
    document.getElementById('ticketCheckin').style.display = 'none';
    document.getElementById('ticketConfirmed').style.display = 'block';
    document.getElementById('ticketWho').textContent = localStorage.getItem('sr_ticket_' + SPRINT);
    renderVoteSummary();
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
  var tKey = 'sr_ticket_' + SPRINT, aKey = 'sr_attendees_' + SPRINT;
  function initials(n) {{ return n.split(/\\s+/).map(function(w){{ return w[0]; }}).join('').toUpperCase().slice(0,2); }}
  function firstName(n) {{ return n.split(/\\s+/)[0]; }}
  function renderAvatars() {{
    var att = lsGet(aKey, []);
    document.getElementById('attendeeCount').textContent = att.length + ' of ' + STAKEHOLDERS.length;
    document.getElementById('ticketAvatars').innerHTML = STAKEHOLDERS.map(function(n) {{
      var on = att.indexOf(n) > -1;
      return '<div class="ticket-avatar flex flex-col items-center gap-1' + (on ? '' : ' pending') + '">' +
        '<div class="ticket-initials w-11 h-11 rounded-full bg-surface-container-high border-2 border-secondary flex items-center justify-center font-bold text-xs text-secondary">' + initials(n) + '</div>' +
        '<div class="ticket-name text-[10px] text-surface/50 max-w-16 truncate">' + firstName(n) + '</div></div>';
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
  var vKey = 'sr_votes_' + SPRINT, mKey = 'sr_my_votes_' + SPRINT;
  function getVotes() {{ return JSON.parse(localStorage.getItem(vKey) || '{{}}'); }}
  function getMyVotes() {{ return JSON.parse(localStorage.getItem(mKey) || '[]'); }}
  function save(v, m) {{ localStorage.setItem(vKey, JSON.stringify(v)); localStorage.setItem(mKey, JSON.stringify(m)); }}
  function render() {{
    var votes = getVotes(), my = getMyVotes();
    var vals = Object.values(votes), mx = Math.max.apply(null, [1].concat(vals));
    var sorted = Object.entries(votes).sort(function(a,b){{ return b[1]-a[1]; }});
    var topKey = sorted.length && sorted[0][1] > 0 ? sorted[0][0] : null;
    container.querySelectorAll('.ballot-item').forEach(function(item) {{
      var k = item.dataset.key, c = votes[k] || 0, voted = my.indexOf(k) > -1, isTop = k === topKey;
      item.querySelector('.ballot-vote-count').textContent = c;
      item.querySelector('.ballot-vote-btn').classList.toggle('voted', voted);
      item.querySelector('.ballot-bar-fill').style.width = (c / mx * 100) + '%';
      var tb = item.querySelector('.top-pick'); if (tb) tb.style.display = isTop ? 'inline-block' : 'none';
      var vb = item.querySelector('.voted-badge'); if (vb) vb.style.display = voted ? 'inline-block' : 'none';
      item.style.order = -c;
    }});
  }}
  container.addEventListener('click', function(e) {{
    var btn = e.target.closest('.ballot-vote-btn');
    if (!btn) return;
    var k = btn.dataset.key, v = getVotes(), m = getMyVotes(), i = m.indexOf(k);
    if (i > -1) {{ m.splice(i, 1); v[k] = Math.max(0, (v[k] || 0) - 1); }}
    else {{ m.push(k); v[k] = (v[k] || 0) + 1; }}
    save(v, m); render();
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
  var saved = localStorage.getItem('sr_ticket_' + SPRINT);
  if (saved && nameInput) nameInput.value = saved;
  function getFb() {{ return lsGet(fbKey, []); }}
  function render() {{
    var items = getFb();
    if (!items.length) {{ entries.innerHTML = '<div class="text-center text-on-surface-variant italic py-4 text-sm">No feedback yet &mdash; be the first.</div>'; return; }}
    entries.innerHTML = items.map(function(it) {{
      return '<div class="border-l-4 border-primary pl-4 mb-4 space-y-1"><div class="flex justify-between items-center"><span class="text-sm font-label font-black text-primary uppercase">' + it.name + '</span><span class="text-[11px] font-label text-on-surface-variant font-bold uppercase">' + it.time + '</span></div><p class="text-on-surface font-headline">&ldquo;' + it.text + '&rdquo;</p></div>';
    }}).join('');
  }}
  submitBtn.addEventListener('click', function() {{
    var name = nameInput.value.trim(), text = textInput.value.trim();
    if (!name || !text) return;
    var items = getFb(), now = new Date();
    var ts = now.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }}) + ' at ' + now.toLocaleTimeString('en-US', {{ hour: 'numeric', minute: '2-digit' }});
    items.push({{ name: name, text: text.replace(/</g, '&lt;').replace(/>/g, '&gt;'), time: ts }});
    lsSet(fbKey, items); textInput.value = ''; render();
  }});
  textInput.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submitBtn.click();
  }});
  render();
}})();
}} // end initInteractive
</script>
</body>
</html>'''

    return html


def generate_index(all_sprint_metrics):
    """Generate an index.html listing all sprints."""
    rows = ""
    for m in reversed(all_sprint_metrics):
        sprint = m["sprint"]
        fname = config.sprint_to_filename(sprint["name"])
        rows += f'''<tr class="hover:bg-white/[0.03] transition-colors">
  <td class="px-8 py-5"><a href="{fname}" class="text-secondary font-bold hover:underline">{_esc(sprint["name"])}</a></td>
  <td class="px-8 py-5">{m["sprint_date_range"]}</td>
  <td class="px-8 py-5 text-secondary font-headline font-black text-2xl">{m["grade"]}</td>
  <td class="px-8 py-5">{_esc(m["grade_label"])}</td>
  <td class="px-8 py-5">{m["completion_rate"]:.0f}%</td>
  <td class="px-8 py-5">{m["points_completed"]:.0f}/{m["points_committed"]:.0f}</td>
</tr>\n'''

    return f'''<!DOCTYPE html>
<html class="dark" lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sprint Reviews</title>
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400..800&family=Space+Grotesk:wght@300..700&display=swap" rel="stylesheet">
<script>
tailwind.config = {{
  darkMode: "class",
  theme: {{
    extend: {{
      colors: {{
        "primary": "#D32F2F",
        "secondary": "#FFD700",
        "surface": "#0a0a0a",
        "surface-container": "#171717",
        "surface-container-high": "#262626",
        "on-surface": "#f5f5f5",
        "on-surface-variant": "#a3a3a3"
      }},
      fontFamily: {{
        "headline": ["Newsreader", "serif"],
        "body": ["Space Grotesk", "sans-serif"],
        "label": ["Space Grotesk", "sans-serif"]
      }},
    }},
  }},
}}
</script>
<style>
  .spotlight-glow {{ background: radial-gradient(circle at 50% 0%, rgba(211,47,47,0.1) 0%, transparent 70%); }}
  ::-webkit-scrollbar {{ width: 8px; }}
  ::-webkit-scrollbar-track {{ background: #0a0a0a; }}
  ::-webkit-scrollbar-thumb {{ background: #262626; border-radius: 10px; }}
</style>
</head>
<body class="bg-surface text-on-surface font-body">
<div class="relative overflow-hidden spotlight-glow p-20 text-center border-b border-white/5">
  <h1 class="text-7xl font-headline font-black text-on-surface tracking-tighter">Sprint Reviews</h1>
  <p class="text-on-surface-variant font-label uppercase tracking-[0.3em] text-sm mt-4">{_esc(config.TEAM_NAME)}</p>
</div>
<div class="max-w-5xl mx-auto py-12 px-6">
  <div class="bg-surface-container-high rounded-3xl overflow-hidden border border-white/5">
    <table class="w-full text-left font-label">
      <thead class="bg-black/40 text-[11px] uppercase tracking-widest text-on-surface-variant border-b border-white/5">
        <tr><th class="px-8 py-5">Sprint</th><th class="px-8 py-5">Dates</th><th class="px-8 py-5">Grade</th><th class="px-8 py-5">Rating</th><th class="px-8 py-5">Completion</th><th class="px-8 py-5">Points</th></tr>
      </thead>
      <tbody class="divide-y divide-white/5">{rows}</tbody>
    </table>
  </div>
</div>
<footer class="text-center py-12 text-on-surface-variant text-sm border-t border-white/5">
  Generated automatically by Sprint Review Automation &middot; {datetime.now().strftime("%B %d, %Y")}
</footer>
</body>
</html>'''


# ── Private helpers ──

def _esc(s):
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _extract_description(desc):
    if not desc or not isinstance(desc, dict):
        return ""
    text = ""
    for block in desc.get("content", []):
        for item in block.get("content", []):
            if item.get("type") == "text":
                text += item.get("text", "")
    return (text[:200] + "...") if len(text) > 200 else text


def _first_sentence(text):
    if not text:
        return ""
    import re
    m = re.match(r"(.+?[.!?])\s", text)
    sentence = m.group(1) if m else text
    if len(sentence) > 150:
        sentence = sentence[:147] + "..."
    return sentence


def _build_awards_html(s, sprint_index=0):
    mvp = s["mvp"]
    workhorse = s["workhorse"]
    speed_demon = s["speed_demon"]

    if not mvp and not workhorse and not speed_demon:
        return ""

    pool_size = len(config.MVP_GIFS)
    gi = sprint_index % pool_size
    mvp_gif = config.MVP_GIFS[gi]
    speed_gif = config.SPEED_DEMON_GIFS[gi]
    work_gif = config.WORKHORSE_GIFS[gi]

    cards = []

    if mvp:
        cards.append(f'''    <div class="group relative bg-surface-container-high rounded-3xl overflow-hidden p-8 text-center space-y-6 border border-white/5 hover:border-secondary/40 transition-all duration-500">
      <div class="relative w-full aspect-video mx-auto rounded-xl overflow-hidden border-2 border-secondary shadow-[0_0_40px_rgba(255,215,0,0.15)] group-hover:scale-[1.03] transition-transform">
        <img alt="MVP" class="w-full h-full object-contain bg-black" src="{mvp_gif}">
      </div>
      <div class="space-y-2">
        <span class="font-label text-xs uppercase tracking-[0.3em] text-secondary font-black">Most Valuable Player</span>
        <h4 class="text-xl font-headline font-bold text-on-surface">{_esc(mvp[0])}</h4>
        <p class="text-on-surface-variant text-sm">{mvp[1]["points_share"]:.1f} points &middot; {mvp[1]["subtasks_done"]} sub-tasks</p>
      </div>
    </div>''')

    if speed_demon:
        cards.append(f'''    <div class="group relative bg-surface-container-high rounded-3xl overflow-hidden p-8 text-center space-y-6 border border-white/5 hover:border-primary/40 transition-all duration-500">
      <div class="relative w-full aspect-video mx-auto rounded-xl overflow-hidden border-2 border-primary shadow-[0_0_40px_rgba(211,47,47,0.15)] group-hover:scale-[1.03] transition-transform">
        <img alt="Speed Demon" class="w-full h-full object-contain bg-black" src="{speed_gif}">
      </div>
      <div class="space-y-2">
        <span class="font-label text-xs uppercase tracking-[0.3em] text-primary font-black">Speed Demon</span>
        <h4 class="text-xl font-headline font-bold text-on-surface">{_esc(speed_demon[0])}</h4>
        <p class="text-on-surface-variant text-sm">Avg {speed_demon[1]:.1f} day cycle time</p>
      </div>
    </div>''')

    if workhorse:
        cards.append(f'''    <div class="group relative bg-surface-container-high rounded-3xl overflow-hidden p-8 text-center space-y-6 border border-white/5 hover:border-secondary/40 transition-all duration-500">
      <div class="relative w-full aspect-video mx-auto rounded-xl overflow-hidden border-2 border-secondary shadow-[0_0_40px_rgba(255,215,0,0.15)] group-hover:scale-[1.03] transition-transform">
        <img alt="Workhorse" class="w-full h-full object-contain bg-black" src="{work_gif}">
      </div>
      <div class="space-y-2">
        <span class="font-label text-xs uppercase tracking-[0.3em] text-secondary font-black">The Workhorse</span>
        <h4 class="text-xl font-headline font-bold text-on-surface">{_esc(workhorse[0])}</h4>
        <p class="text-on-surface-variant text-sm">{workhorse[1]["subtasks_done"]} sub-tasks completed</p>
      </div>
    </div>''')

    return f'''<section class="space-y-12">
  <h3 class="text-center font-headline font-black text-5xl text-on-surface tracking-tight uppercase italic">Academy Awards</h3>
  <div class="grid md:grid-cols-{len(cards)} gap-8">
{chr(10).join(cards)}
  </div>
</section>'''
