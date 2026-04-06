"""
connectors/jira_connector.py
============================
Fetches all issues from your Jira Cloud project and converts them
into the JSON format the MCP pipeline expects.

Credentials come from the .env file in the project root.
See .env.example for setup instructions.

Main function:
    fetch_jira_project()  ->  dict  (ready to save as project JSON)
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# Load .env from project root (one directory up from connectors/)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")

# ── Read credentials from environment ─────────────────────────────────────────
DOMAIN           = os.getenv("ATLASSIAN_DOMAIN", "").rstrip("/")
EMAIL            = os.getenv("ATLASSIAN_EMAIL", "")
TOKEN            = os.getenv("ATLASSIAN_API_TOKEN", "")
PROJECT_KEY      = os.getenv("JIRA_PROJECT_KEY", "").strip().upper()
DEADLINE         = os.getenv("JIRA_DEADLINE", "").strip()
HOURS_PER_WEEK   = int(os.getenv("JIRA_HOURS_PER_WEEK", "40") or 40)


# ── Jira status  →  internal status ───────────────────────────────────────────
# Add any custom Jira statuses your team uses to the right category below.
_STATUS_MAP = {
    # Done / closed
    "done":        "Done",
    "closed":      "Done",
    "resolved":    "Done",
    "fixed":       "Done",
    "complete":    "Done",
    "completed":   "Done",
    "won't fix":   "Done",
    "wont fix":    "Done",
    "invalid":     "Done",
    "duplicate":   "Done",

    # In Progress
    "in progress":    "In Progress",
    "in development": "In Progress",
    "in review":      "In Progress",
    "in testing":     "In Progress",
    "review":         "In Progress",
    "development":    "In Progress",
    "testing":        "In Progress",
    "code review":    "In Progress",
    "qa":             "In Progress",
    "under review":   "In Progress",
    "selected for development": "In Progress",

    # Blocked / paused
    "blocked":    "Blocked",
    "on hold":    "Blocked",
    "waiting":    "Blocked",
    "impediment": "Blocked",
    "hold":       "Blocked",
    "paused":     "Blocked",
}


def _map_status(jira_status: str) -> str:
    """Convert any Jira status name to Done / In Progress / Blocked / To Do."""
    return _STATUS_MAP.get(jira_status.lower().strip(), "To Do")


def _seconds_to_hours(seconds) -> float:
    """Convert Jira time-tracking seconds to hours (1 decimal place)."""
    if seconds and int(seconds) > 0:
        return round(int(seconds) / 3600, 1)
    return 0.0


def _check_credentials():
    """Print a clear error and exit if any required .env variable is missing."""
    missing = []
    if not DOMAIN:
        missing.append("ATLASSIAN_DOMAIN  (e.g. https://yourcompany.atlassian.net)")
    if not EMAIL:
        missing.append("ATLASSIAN_EMAIL   (e.g. you@example.com)")
    if not TOKEN:
        missing.append("ATLASSIAN_API_TOKEN")
    if not PROJECT_KEY:
        missing.append("JIRA_PROJECT_KEY  (e.g. MYPROJ)")

    if missing:
        print("\n[ERROR] Missing values in your .env file:")
        for m in missing:
            print(f"        {m}")
        print("\nOpen the .env file and fill in the missing values.")
        print("See .env.example for a complete template.\n")
        sys.exit(1)


# ── Low-level HTTP helper ──────────────────────────────────────────────────────

def _request(method: str, path: str, params: dict = None, json_body: dict = None) -> dict:
    """
    Make an authenticated GET or POST request to the Jira REST API.
    Raises friendly errors for common problems (bad token, wrong key, etc).
    """
    url  = f"{DOMAIN}/rest/api/3{path}"
    auth = HTTPBasicAuth(EMAIL, TOKEN)
    hdrs = {"Accept": "application/json", "Content-Type": "application/json"}

    try:
        if method.upper() == "POST":
            r = requests.post(url, headers=hdrs, auth=auth,
                              json=json_body or {}, timeout=20)
        else:
            r = requests.get(url, headers=hdrs, auth=auth,
                             params=params or {}, timeout=20)
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Cannot connect to: {DOMAIN}")
        print("  - Check that ATLASSIAN_DOMAIN is spelled correctly in .env")
        print("  - Check your internet connection\n")
        sys.exit(1)

    if r.status_code == 401:
        print("\n[ERROR] Jira said: 401 Unauthorized")
        print("  Your API token or email is wrong.")
        print("  - Double-check ATLASSIAN_EMAIL in .env")
        print("  - Generate a fresh token at: https://id.atlassian.com/manage-profile/security/api-tokens\n")
        sys.exit(1)

    if r.status_code == 403:
        print(f"\n[ERROR] Jira said: 403 Forbidden (project: {PROJECT_KEY})")
        print("  Your account does not have permission to view this project.\n")
        sys.exit(1)

    if r.status_code == 404:
        print(f"\n[ERROR] Jira said: 404 Not Found for project '{PROJECT_KEY}'")
        print("  - Check that JIRA_PROJECT_KEY is the short code (e.g. MYPROJ, not 'My Project')")
        print("  - In Jira: Project Settings > Details > Key\n")
        sys.exit(1)

    r.raise_for_status()
    return r.json()


def _get(path: str, params: dict = None) -> dict:
    return _request("GET", path, params=params)


def _post(path: str, body: dict = None) -> dict:
    return _request("POST", path, json_body=body)


# ── Individual fetchers ────────────────────────────────────────────────────────

def _fetch_project_meta() -> dict:
    """Fetch project name and description from Jira. Build deadline and source."""
    data = _get(f"/project/{PROJECT_KEY}")

    deadline = DEADLINE or (datetime.today() + timedelta(days=90)).strftime("%Y-%m-%d")

    return {
        "id":          PROJECT_KEY.lower(),
        "name":        data.get("name", PROJECT_KEY),
        "description": (data.get("description") or "").strip(),
        "status":      "In Progress",
        "start_date":  "",
        "deadline":    deadline,
        "source": {
            "type":        "jira_live",
            "domain":      DOMAIN,
            "project_key": PROJECT_KEY,
            "fetched_at":  datetime.today().strftime("%Y-%m-%d"),
        },
    }


def _fetch_all_issues() -> list:
    """
    Fetch every issue in the project using the Jira Cloud search/jql endpoint.

    This endpoint uses cursor-based pagination:
      - Response contains 'nextPageToken' and 'isLast'
      - Pass nextPageToken in the next request body to get the next page
    """
    all_issues = []
    page_size  = 50
    fields = [
        "summary", "status", "priority", "assignee", "issuetype",
        "created", "resolutiondate",
        "timeoriginalestimate", "timespent",
        "customfield_10016", "customfield_10028",   # story points
        "labels",
    ]

    next_page_token = None

    while True:
        body = {
            "jql":        f"project = {PROJECT_KEY} ORDER BY created DESC",
            "maxResults": page_size,
            "fields":     fields,
        }
        if next_page_token:
            body["nextPageToken"] = next_page_token

        data  = _post("/search/jql", body)
        batch = data.get("issues", [])
        all_issues.extend(batch)

        print(f"    Fetched {len(all_issues)} issues ...", end="\r")

        if data.get("isLast", True) or not batch:
            break

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    print(f"    Fetched {len(all_issues)} issues.    ")
    return all_issues


def _convert_issue(item: dict) -> dict:
    """Convert one raw Jira issue into an MCP task dict."""
    f           = item["fields"]
    jira_status = f["status"]["name"]
    status      = _map_status(jira_status)

    # ── Time estimate ──────────────────────────────────────────────────────────
    # Priority order: logged original estimate → story points × 4 → default 8h
    est_secs = f.get("timeoriginalestimate") or 0
    if est_secs:
        estimated_hours = _seconds_to_hours(est_secs)
    else:
        story_pts = f.get("customfield_10016") or f.get("customfield_10028") or 0
        estimated_hours = float(story_pts) * 4.0 if story_pts else 8.0

    # ── Actual time (only for Done tasks) ─────────────────────────────────────
    actual_hours = None
    if status == "Done":
        spent_secs = f.get("timespent") or 0
        if spent_secs:
            actual_hours = _seconds_to_hours(spent_secs)

    # ── Assignee ──────────────────────────────────────────────────────────────
    assignee    = f.get("assignee")
    assigned_to = assignee["displayName"] if assignee else "Unassigned"

    return {
        "id":             item["key"],
        "title":          f.get("summary", "(no title)"),
        "type":           f["issuetype"]["name"],
        "status":         status,
        "jira_status":    jira_status,          # original Jira status (for debug)
        "priority":       (f.get("priority") or {}).get("name", "Medium"),
        "assigned_to":    assigned_to,
        "estimated_time": estimated_hours,
        "actual_time":    actual_hours,
        "created":        (f.get("created") or "")[:10],
        "resolved":       (f.get("resolutiondate") or "")[:10] or None,
        "labels":         f.get("labels", []),
        "_real":          True,
        "_source":        f"Jira API ({DOMAIN}/browse/{item['key']})",
    }


def _build_team(tasks: list) -> list:
    """
    Build the team list from the unique assignees found in tasks.
    Everyone gets HOURS_PER_WEEK capacity (from .env, default 40).
    """
    seen = {}
    for task in tasks:
        name = task["assigned_to"]
        if name not in ("Unassigned", "") and name not in seen:
            seen[name] = {
                "id":                      name.lower().replace(" ", "_"),
                "name":                    name,
                "role":                    "Team Member",
                "capacity_hours_per_week": HOURS_PER_WEEK,
            }

    team = list(seen.values())

    if not team:
        # Nobody is assigned — create one placeholder so pipeline doesn't break
        team = [{
            "id":                      "unassigned",
            "name":                    "Unassigned",
            "role":                    "Team Member",
            "capacity_hours_per_week": HOURS_PER_WEEK,
        }]

    return team


# ── Main public function ───────────────────────────────────────────────────────

def fetch_jira_project(verbose: bool = True) -> dict:
    """
    Fetch the complete Jira project and return it as an MCP-compatible dict.

    Args:
        verbose: print progress messages (True when running standalone)

    Returns:
        {
            "project": {...},
            "tasks":   [...],
            "team":    [...],
        }
    """
    _check_credentials()

    if verbose:
        print(f"  Connecting to : {DOMAIN}")
        print(f"  Project key   : {PROJECT_KEY}")
        print()

    # 1. Project metadata
    if verbose:
        print("  [1/3] Fetching project info ...")
    project = _fetch_project_meta()
    if verbose:
        print(f"        Name     : {project['name']}")
        print(f"        Deadline : {project['deadline']}")
        print()

    # 2. Issues
    if verbose:
        print("  [2/3] Fetching issues ...")
    raw_issues = _fetch_all_issues()
    tasks      = [_convert_issue(i) for i in raw_issues]

    if verbose:
        done_n  = sum(1 for t in tasks if t["status"] == "Done")
        prog_n  = sum(1 for t in tasks if t["status"] == "In Progress")
        block_n = sum(1 for t in tasks if t["status"] == "Blocked")
        todo_n  = sum(1 for t in tasks if t["status"] == "To Do")
        print(f"        {len(tasks)} issues: "
              f"{done_n} done | {prog_n} in-progress | "
              f"{block_n} blocked | {todo_n} to-do")
        print()

    # 3. Team
    if verbose:
        print("  [3/3] Building team from assignees ...")
    team = _build_team(tasks)
    if verbose:
        names = ", ".join(m["name"] for m in team)
        print(f"        {len(team)} member(s): {names}")
        print()

    return {"project": project, "tasks": tasks, "team": team}
