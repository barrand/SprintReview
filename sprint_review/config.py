"""Configuration: loads environment variables and defines constants."""

import os
import re
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "").strip()
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "").strip()

SP_FIELD = "customfield_10041"

ISSUE_FIELDS = f"summary,status,assignee,issuetype,priority,{SP_FIELD},parent,description,attachment"
LIGHTWEIGHT_FIELDS = f"summary,status,issuetype,{SP_FIELD},assignee"

BUG_ISSUE_TYPES = {"Defect", "Bug"}

TEAM_NAME = "A Mobile Masters Production"

OUTPUT_DIR = "output"
CACHE_DIR = os.path.join(OUTPUT_DIR, ".cache")

GRADE_THRESHOLDS = [
    (95, "A+", "Instant Classic"),
    (90, "A",  "Certified Fresh"),
    (85, "A-", "Critics' Choice"),
    (80, "B+", "Crowd Pleaser"),
    (75, "B",  "Worth the Ticket"),
    (70, "B-", "Solid Matinee"),
    (60, "C+", "Mixed Reviews"),
    (50, "C",  "Needs a Sequel"),
    (40, "D",  "Straight to DVD"),
    (0,  "F",  "Box Office Bomb"),
]

GOAL_MET_THRESHOLD = 70

MVP_GIFS = [
    "https://media.giphy.com/media/lXo8uSnIkaB9e/giphy.gif",           # Iron Man suit-up
    "https://media.giphy.com/media/g9LvKF4SPTK0KOIFdh/giphy.gif",      # Captain America shield
    "https://media.giphy.com/media/xThtavMQZtCbNZo2WY/giphy.gif",      # Black Panther Wakanda Forever
    "https://media.giphy.com/media/l0HlGreOkzgb64A8w/giphy.gif",       # Wonder Woman
    "https://media.giphy.com/media/10bKPDUM5H7m7u/giphy.gif",          # Superman flying
    "https://media.giphy.com/media/XHxfmR19vnu6mzaNWk/giphy.gif",      # Thor hammer
]

SPEED_DEMON_GIFS = [
    "https://media.giphy.com/media/ICoxhc8wGbJ8k/giphy.gif",           # The Flash running
    "https://media.giphy.com/media/3oriNYQX2lC6dfW2Ji/giphy.gif",      # Quicksilver speeding
    "https://media.giphy.com/media/3oGRFKJ8Ea3hKkLRyE/giphy.gif",      # Quicksilver X-Men Apocalypse
    "https://media.giphy.com/media/eIm624c8nnNbiG0V3g/giphy.gif",      # Neo dodging bullets
    "https://media.giphy.com/media/IxpcUr98ER5ts58uPg/giphy.gif",      # Sonic running
    "https://media.giphy.com/media/yXVO50FJIJMSQ/giphy.gif",           # Sonic classic
]

WORKHORSE_GIFS = [
    "https://media.giphy.com/media/yoJC2JaiEMoxIhQhY4/giphy.gif",      # Rocky champion
    "https://media.giphy.com/media/382KHGeAfisOk/giphy.gif",            # Rocky training
    "https://media.giphy.com/media/S819XcxYIRX9e/giphy.gif",            # Creed training
    "https://media.giphy.com/media/1swY684seKPWWMmTRj/giphy.gif",       # Rocky punching
    "https://media.giphy.com/media/W9G8OK82R3dfO/giphy.gif",            # Rocky Balboa
    "https://media.giphy.com/media/26tPsS788ZFNT0nU4/giphy.gif",        # Rocky movie official
]


def get_grade(completion_rate):
    for threshold, grade, label in GRADE_THRESHOLDS:
        if completion_rate >= threshold:
            return grade, label
    return "F", "Box Office Bomb"


def sprint_to_filename(sprint_name):
    """Convert sprint name to a safe filename. e.g. 'FS02: 2026-6' -> 'FS02_2026-6.html'"""
    safe = re.sub(r'[^\w\-]', '_', sprint_name).strip('_')
    safe = re.sub(r'_+', '_', safe)
    return f"{safe}.html"
