"""CLI entrypoint: python -m sprint_review"""

import argparse
import os
import sys

from . import config
from .jira_client import JiraClient
from .analytics import compute
from .dashboard import generate, generate_index


def main():
    parser = argparse.ArgumentParser(
        description="Sprint Review Automation -- generate HTML dashboards from Jira sprint data"
    )
    parser.add_argument("--board-id", type=int, required=True, help="Jira board ID")
    parser.add_argument("--sprint", type=str, default=None, help="Target sprint name (default: latest closed)")
    parser.add_argument("--all", action="store_true", help="Generate for all closed sprints + index")
    parser.add_argument("--count", type=int, default=6, help="Number of sprints to fetch for velocity (default: 6)")

    args = parser.parse_args()

    if not config.JIRA_BASE_URL or not config.JIRA_EMAIL or not config.JIRA_API_TOKEN:
        print("Error: Missing Jira credentials. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN in .env")
        sys.exit(1)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    client = JiraClient()

    if args.all:
        _generate_all(client, args.board_id, args.count)
    else:
        _generate_single(client, args.board_id, args.sprint, args.count)


def _generate_single(client, board_id, target_sprint_name, sprint_count):
    """Generate a single sprint review."""
    data = client.fetch_sprint_data(board_id, target_sprint=target_sprint_name, sprint_count=sprint_count)

    all_sprints = data["all_sprints"]
    target_id = data["target_sprint"]["id"]
    target_idx = next(i for i, s in enumerate(all_sprints) if s["id"] == target_id)
    data["sprint_index"] = target_idx

    metrics = compute(data)

    prev_fname = config.sprint_to_filename(all_sprints[target_idx - 1]["name"]) if target_idx > 0 else None
    next_fname = None
    if target_idx < len(all_sprints) - 1:
        next_fname = config.sprint_to_filename(all_sprints[target_idx + 1]["name"])
    elif data.get("next_sprint"):
        next_fname = config.sprint_to_filename(data["next_sprint"]["name"])

    html = generate(metrics, prev_filename=prev_fname, next_filename=next_fname)
    fname = config.sprint_to_filename(data["target_sprint"]["name"])
    out_path = os.path.join(config.OUTPUT_DIR, fname)

    with open(out_path, "w") as f:
        f.write(html)

    print(f"\nGenerated: {out_path}")
    print(f"Sprint: {data['target_sprint']['name']}")
    print(f"Grade: {metrics['grade']} ({metrics['grade_label']})")
    print(f"Stories: {len(metrics['done_stories'])}/{len(metrics['stories'])} done")
    print(f"Points: {metrics['points_completed']:.0f}/{metrics['points_committed']:.0f}")


def _generate_all(client, board_id, sprint_count):
    """Generate reports for all recent closed sprints + an index page.
    Uses sprint_count to determine how far back to go (default 6)."""
    print("Fetching closed sprints...")
    closed = client.fetch_closed_sprints(board_id, limit=sprint_count)
    active_future = client.fetch_active_and_future(board_id)

    if not closed:
        print("No closed sprints found.")
        sys.exit(1)

    print(f"Found {len(closed)} sprints to process. Generating reports...\n")

    all_metrics = []

    for idx, sprint in enumerate(closed):
        print(f"[{idx + 1}/{len(closed)}] Processing '{sprint['name']}'...")

        try:
            data = client.fetch_sprint_data(
                board_id,
                target_sprint=sprint["name"],
                sprint_count=sprint_count,
            )
            data["sprint_index"] = idx
            metrics = compute(data)
            all_metrics.append(metrics)

            prev_fname = config.sprint_to_filename(closed[idx - 1]["name"]) if idx > 0 else None
            next_fname = None
            if idx < len(closed) - 1:
                next_fname = config.sprint_to_filename(closed[idx + 1]["name"])
            elif active_future:
                next_fname = config.sprint_to_filename(active_future[0]["name"])

            html = generate(metrics, prev_filename=prev_fname, next_filename=next_fname)
            fname = config.sprint_to_filename(sprint["name"])
            out_path = os.path.join(config.OUTPUT_DIR, fname)

            with open(out_path, "w") as f:
                f.write(html)

            print(f"  -> {fname} ({metrics['grade']} - {metrics['grade_label']})")

        except Exception as e:
            print(f"  -> FAILED: {e}")

    if all_metrics:
        index_html = generate_index(all_metrics)
        index_path = os.path.join(config.OUTPUT_DIR, "index.html")
        with open(index_path, "w") as f:
            f.write(index_html)
        print(f"\nGenerated index: {index_path}")

    print(f"\nDone! Generated {len(all_metrics)} sprint reviews in {config.OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
