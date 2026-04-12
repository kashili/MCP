#!/usr/bin/env python3
"""
upload_jira_data.py
===================
Reads the "Jira Tickets" sheet from the Release Management Platform Excel file
and uploads all data into a Jira Cloud (or Server/Data Center) instance.

Steps performed:
  1. Ensure Fix Versions exist in each project.
  2. Create all issues (Stories, Bugs, Tasks, Test Executions).
  3. Transition issues to their target status (Done, In Progress, etc.).
  4. Create issue links (blocks, depends-on, relates-to, test-coverage).

Prerequisites:
  - pip install openpyxl requests
  - A Jira instance with projects ATLAS, BEACON, CIPHER, DELTA already created.
  - For Jira Cloud: an API token (https://id.atlassian.com/manage-profile/security/api-tokens)
  - For Jira Server/DC: a personal access token or basic-auth credentials.

Usage:
  1. Copy .env.example to .env and fill in your values, OR export env vars directly.
  2. python upload_jira_data.py --file Release_Management_Platform_Sample_Data.xlsx
# Jira connection settings
# Copy this file to .env and fill in your values.

# Jira Cloud:  https://yourcompany.atlassian.net
# Jira Server: https://jira.yourcompany.com
JIRA_BASE_URL=https://yourcompany.atlassian.net

# Your Jira login email (Cloud) or username (Server/DC)
JIRA_USER_EMAIL=you@company.com

# Jira Cloud: API token from https://id.atlassian.com/manage-profile/security/api-tokens
# Jira Server/DC: personal access token
JIRA_API_TOKEN=your-api-token-here

# Set to "true" to log actions without making any API calls
DRY_RUN=false

"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import openpyxl
import requests
from requests.auth import HTTPBasicAuth

# ---------------------------------------------------------------------------
# Configuration — override via environment variables or .env file
# ---------------------------------------------------------------------------
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")          # e.g. https://yourcompany.atlassian.net
JIRA_USER_EMAIL = os.getenv("JIRA_USER_EMAIL", "")       # e.g. you@company.com
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")         # API token (Cloud) or PAT (Server)
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jira-uploader")

# ---------------------------------------------------------------------------
# Fix-version metadata per project (from the "Project Overview" sheet)
# ---------------------------------------------------------------------------
FIX_VERSIONS = {
    "ATLAS":  {"name": "v3.2 — May 2026 Release", "releaseDate": "2026-05-16",
               "description": "Payment service upgrade with PCI compliance fixes"},
    "BEACON": {"name": "v2.0 — May 2026 Release", "releaseDate": "2026-05-16",
               "description": "Customer portal complete redesign"},
    "CIPHER": {"name": "v1.5 — May 2026 Release", "releaseDate": "2026-05-16",
               "description": "API gateway security hardening"},
    "DELTA":  {"name": "v4.1 — May 2026 Release", "releaseDate": "2026-05-16",
               "description": "Reporting dashboard enhancements"},
}

# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

# Spreadsheet issue types  →  Jira issue-type names.
# Adjust the right-hand side to match your Jira configuration.
ISSUE_TYPE_MAP = {
    "Story":          "Story",
    "Bug":            "Bug",
    "Task":           "Task",
    "Test Execution": "Test Execution",   # Requires Zephyr/Xray or a custom type
}

# Fallback if "Test Execution" doesn't exist — the script will try "Task" instead.
TEST_EXECUTION_FALLBACK = "Task"

# Spreadsheet priority names  →  Jira priority names.
PRIORITY_MAP = {
    "Blocker":  "Blocker",    # or "Highest"
    "Critical": "Critical",   # or "High"
    "High":     "High",
    "Medium":   "Medium",
    "Low":      "Low",
}

# Spreadsheet status  →  Jira transition name(s) to reach that status.
# Jira requires *transitions* rather than direct status edits.
# Each value is a list of transition names to apply in order.
# IMPORTANT: These transition names must match YOUR Jira workflow.
# Common defaults are shown below — adjust as needed.
STATUS_TRANSITIONS = {
    "Open":         [],                                # Default on creation
    "To Do":        [],                                # Often the same as Open/Backlog
    "In Progress":  ["Start Progress"],                # or "In Progress"
    "Done":         ["Start Progress", "Done"],        # or "Resolve Issue", "Close Issue"
    "Passed":       ["Start Progress", "Done"],        # Test Execution: treat like Done
    "Not Started":  [],                                # Default
}

# Link-type mapping:  keyword in spreadsheet  →  Jira link-type name + direction.
# In Jira, an issue link has an "inwardIssue" and "outwardIssue".
# The spreadsheet's "Links" column uses phrases like "Blocks: X", "Depends on: X".
LINK_TYPE_MAP = {
    "blocks":         {"type": "Blocks",    "direction": "outward"},  # this issue blocks target
    "is blocked by":  {"type": "Blocks",    "direction": "inward"},   # this issue is blocked by target
    "depends on":     {"type": "Blocks",    "direction": "inward"},   # alias for "is blocked by"
    "relates to":     {"type": "Relates",   "direction": "outward"},
    "test":           {"type": "Test",      "direction": "outward"},  # test covers story
    "story":          {"type": "Test",      "direction": "inward"},   # story is tested by test
}


# ============================================================================
# Jira REST helpers
# ============================================================================

class JiraClient:
    """Thin wrapper around the Jira REST API."""

    def __init__(self, base_url: str, email: str, token: str, dry_run: bool = False):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(email, token)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        self.dry_run = dry_run
        # Cache: project_key -> {version_name: version_id, ...}
        self._version_cache: dict[str, dict[str, str]] = {}
        # Cache: project_key -> [issue_type_name, ...]
        self._issue_type_cache: dict[str, list[str]] = {}
        # Cache: ticket_key -> issue_id  (populated after creation)
        self.key_to_id: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}/rest/api/2{path}"
        if self.dry_run and method.upper() != "GET":
            log.info("[DRY-RUN] %s %s  body=%s", method, url, kwargs.get("json", ""))
            return None
        resp = requests.request(method, url, auth=self.auth, headers=self.headers, **kwargs)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "5"))
            log.warning("Rate-limited. Sleeping %ds ...", retry_after)
            time.sleep(retry_after)
            return self._request(method, path, **kwargs)
        if resp.status_code >= 400:
            log.error("HTTP %d  %s %s\n  Response: %s", resp.status_code, method, url, resp.text[:500])
        resp.raise_for_status()
        return resp.json() if resp.text else None

    def get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def post(self, path, payload):
        return self._request("POST", path, json=payload)

    def put(self, path, payload):
        return self._request("PUT", path, json=payload)

    # ------------------------------------------------------------------
    # Projects & metadata
    # ------------------------------------------------------------------
    def get_project(self, key: str) -> dict | None:
        """Return project metadata or None if not found."""
        try:
            return self.get(f"/project/{key}")
        except requests.HTTPError:
            return None

    def get_issue_types_for_project(self, project_key: str) -> list[str]:
        """Return list of issue-type names available in a project."""
        if project_key not in self._issue_type_cache:
            meta = self.get(f"/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes")
            names = []
            for proj in meta.get("projects", []):
                for it in proj.get("issuetypes", []):
                    names.append(it["name"])
            self._issue_type_cache[project_key] = names
        return self._issue_type_cache[project_key]

    # ------------------------------------------------------------------
    # Fix Versions
    # ------------------------------------------------------------------
    def ensure_fix_version(self, project_key: str, version_info: dict) -> str:
        """Create a fix version if it doesn't already exist. Returns version id."""
        if project_key not in self._version_cache:
            existing = self.get(f"/project/{project_key}/versions") or []
            self._version_cache[project_key] = {v["name"]: v["id"] for v in existing}

        cache = self._version_cache[project_key]
        if version_info["name"] in cache:
            log.info("Fix version '%s' already exists in %s", version_info["name"], project_key)
            return cache[version_info["name"]]

        proj = self.get_project(project_key)
        payload = {
            "name": version_info["name"],
            "description": version_info.get("description", ""),
            "releaseDate": version_info.get("releaseDate"),
            "released": False,
            "projectId": int(proj["id"]),
        }
        result = self.post("/version", payload)
        vid = result["id"] if result else "dry-run-id"
        cache[version_info["name"]] = vid
        log.info("Created fix version '%s' in %s (id=%s)", version_info["name"], project_key, vid)
        return vid

    # ------------------------------------------------------------------
    # Issue creation
    # ------------------------------------------------------------------
    def resolve_issue_type(self, project_key: str, desired_type: str) -> str:
        """Return a valid issue-type name for the project, with fallback."""
        available = self.get_issue_types_for_project(project_key)
        mapped = ISSUE_TYPE_MAP.get(desired_type, desired_type)
        if mapped in available:
            return mapped
        if desired_type == "Test Execution" and TEST_EXECUTION_FALLBACK in available:
            log.warning(
                "Issue type 'Test Execution' not found in %s — falling back to '%s'",
                project_key, TEST_EXECUTION_FALLBACK,
            )
            return TEST_EXECUTION_FALLBACK
        # Last resort: return as-is and let Jira error
        return mapped

    def create_issue(self, project_key: str, row: dict) -> str | None:
        """
        Create a Jira issue from a spreadsheet row dict.
        Returns the issue key (e.g. "ATLAS-101") or None on failure.
        """
        issue_type = self.resolve_issue_type(project_key, row["Type"])
        fix_version_name = FIX_VERSIONS[project_key]["name"]

        fields = {
            "project":   {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary":   row["Summary"],
            "priority":  {"name": PRIORITY_MAP.get(row["Priority"], row["Priority"])},
            "fixVersions": [{"name": fix_version_name}],
        }

        # Assignee — use the display name from the sheet as the accountId placeholder.
        # In real usage you'd map Dev1 → actual Jira accountId.
        # For now we skip assignee if it's a placeholder like "Dev1".
        assignee = row.get("Assignee", "")
        if assignee and not assignee.startswith("Dev") and not assignee.startswith("QA"):
            fields["assignee"] = {"name": assignee}  # Server/DC
            # For Cloud, use: fields["assignee"] = {"accountId": lookup_account_id(assignee)}

        # Optional: add a label for the milestone
        milestone = row.get("Milestone", "")
        if milestone:
            # Sanitize label (no spaces)
            label = re.sub(r"[^A-Za-z0-9_-]", "_", milestone)
            fields["labels"] = [label]

        payload = {"fields": fields}
        log.info("Creating %s %s: %s", issue_type, row["Ticket Key"], row["Summary"])

        try:
            result = self.post("/issue", payload)
            if result:
                created_key = result["key"]
                self.key_to_id[created_key] = result["id"]
                log.info("  → Created %s (id=%s)", created_key, result["id"])
                return created_key
            else:
                # dry-run
                self.key_to_id[row["Ticket Key"]] = f"dry-{row['Ticket Key']}"
                return row["Ticket Key"]
        except requests.HTTPError as exc:
            log.error("  ✗ Failed to create %s: %s", row["Ticket Key"], exc)
            return None

    # ------------------------------------------------------------------
    # Transitions (status changes)
    # ------------------------------------------------------------------
    def get_transitions(self, issue_key: str) -> dict[str, str]:
        """Return {transition_name_lower: transition_id} for the issue."""
        data = self.get(f"/issue/{issue_key}/transitions")
        return {t["name"].lower(): t["id"] for t in (data or {}).get("transitions", [])}

    def transition_issue(self, issue_key: str, target_status: str):
        """Move an issue through the workflow to reach target_status."""
        transition_names = STATUS_TRANSITIONS.get(target_status, [])
        if not transition_names:
            return  # Already in default state

        for tname in transition_names:
            available = self.get_transitions(issue_key)
            tid = available.get(tname.lower())
            if tid:
                self.post(f"/issue/{issue_key}/transitions", {"transition": {"id": tid}})
                log.info("  → Transitioned %s via '%s'", issue_key, tname)
            else:
                # Try fuzzy match
                matched = False
                for avail_name, avail_id in available.items():
                    if tname.lower() in avail_name or avail_name in tname.lower():
                        self.post(f"/issue/{issue_key}/transitions", {"transition": {"id": avail_id}})
                        log.info("  → Transitioned %s via '%s' (fuzzy matched from '%s')",
                                 issue_key, avail_name, tname)
                        matched = True
                        break
                if not matched:
                    log.warning("  ⚠ Transition '%s' not found for %s. Available: %s",
                                tname, issue_key, list(available.keys()))

    # ------------------------------------------------------------------
    # Issue links
    # ------------------------------------------------------------------
    def create_issue_link(self, link_type_name: str, inward_key: str, outward_key: str):
        """Create a link between two issues."""
        payload = {
            "type": {"name": link_type_name},
            "inwardIssue":  {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        log.info("  → Linking %s —[%s]→ %s", inward_key, link_type_name, outward_key)
        try:
            self.post("/issueLink", payload)
        except requests.HTTPError as exc:
            log.error("  ✗ Failed to link %s → %s: %s", inward_key, outward_key, exc)


# ============================================================================
# Excel parsing
# ============================================================================

def read_jira_sheet(file_path: str) -> list[dict]:
    """Read 'Jira Tickets' sheet and return a list of row dicts."""
    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb["Jira Tickets"]
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h).strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        record = {}
        for i, val in enumerate(row):
            record[headers[i]] = str(val).strip() if val is not None else ""
        data.append(record)
    wb.close()
    return data


def parse_links(links_cell: str) -> list[dict]:
    """
    Parse the 'Links' column into structured link info.

    Examples:
        "Test: ATLAS-201"                    → [{"keyword": "test", "target": "ATLAS-201"}]
        "Test: ATLAS-202, Blocks: BEACON-105" → two entries
        "Is blocked by: ATLAS-102"           → [{"keyword": "is blocked by", "target": "ATLAS-102"}]
        "Depends on: CIPHER-104"             → [{"keyword": "depends on", "target": "CIPHER-104"}]
        "Story: ATLAS-101"                   → [{"keyword": "story", "target": "ATLAS-101"}]
        "—" or "None" or ""                  → []
    """
    if not links_cell or links_cell in ("—", "None", "N/A", ""):
        return []

    results = []
    # Split on comma, then parse each segment
    segments = [s.strip() for s in links_cell.split(",")]
    for seg in segments:
        # Match pattern like "Keyword: PROJ-123" (keyword may be multi-word)
        match = re.match(r"^(.+?):\s*([A-Z]+-\d+)$", seg.strip(), re.IGNORECASE)
        if match:
            keyword = match.group(1).strip().lower()
            target = match.group(2).strip().upper()
            results.append({"keyword": keyword, "target": target})
        else:
            log.debug("Could not parse link segment: '%s'", seg)
    return results


# ============================================================================
# Orchestration
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Upload Jira data from Excel to Jira.")
    parser.add_argument("--file", "-f", required=True, help="Path to the .xlsx file")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without making API calls")
    parser.add_argument("--skip-transitions", action="store_true",
                        help="Skip status transitions (create issues in default state only)")
    parser.add_argument("--skip-links", action="store_true",
                        help="Skip issue link creation")
    args = parser.parse_args()

    # --- Load environment from .env file if present -----------------------
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        log.info("Loading config from %s", env_path)
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    # Re-read after potential .env load
    base_url = os.getenv("JIRA_BASE_URL", JIRA_BASE_URL)
    email    = os.getenv("JIRA_USER_EMAIL", JIRA_USER_EMAIL)
    token    = os.getenv("JIRA_API_TOKEN", JIRA_API_TOKEN)
    dry_run  = args.dry_run or DRY_RUN

    if not base_url or not email or not token:
        log.error(
            "Missing Jira credentials. Set JIRA_BASE_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN "
            "as environment variables or in a .env file."
        )
        sys.exit(1)

    client = JiraClient(base_url, email, token, dry_run=dry_run)

    if dry_run:
        log.info("=== DRY-RUN MODE — no changes will be made ===")

    # --- Step 0: Validate file exists -------------------------------------
    file_path = args.file
    if not Path(file_path).exists():
        log.error("File not found: %s", file_path)
        sys.exit(1)

    # --- Step 1: Read Excel -----------------------------------------------
    log.info("Reading Jira Tickets from: %s", file_path)
    tickets = read_jira_sheet(file_path)
    log.info("Found %d tickets across projects.", len(tickets))

    # --- Step 2: Verify projects exist ------------------------------------
    projects = sorted(set(t["Project"] for t in tickets))
    log.info("Projects referenced: %s", projects)
    for pkey in projects:
        proj = client.get_project(pkey)
        if proj is None and not dry_run:
            log.error(
                "Project %s does not exist in Jira. Please create it first "
                "(key=%s) and re-run.", pkey, pkey
            )
            sys.exit(1)
        else:
            log.info("Project %s: OK", pkey)

    # --- Step 3: Ensure fix versions exist --------------------------------
    log.info("\n--- Creating / verifying Fix Versions ---")
    for pkey in projects:
        if pkey in FIX_VERSIONS:
            client.ensure_fix_version(pkey, FIX_VERSIONS[pkey])

    # --- Step 4: Create issues --------------------------------------------
    log.info("\n--- Creating Issues ---")
    created_keys = []
    failed_keys = []
    for ticket in tickets:
        key = client.create_issue(ticket["Project"], ticket)
        if key:
            created_keys.append(key)
        else:
            failed_keys.append(ticket["Ticket Key"])

    log.info("Created %d issues, %d failures.", len(created_keys), len(failed_keys))
    if failed_keys:
        log.warning("Failed tickets: %s", failed_keys)

    # --- Step 5: Transition issues to target statuses ---------------------
    if not args.skip_transitions:
        log.info("\n--- Transitioning Issues to Target Statuses ---")
        for ticket in tickets:
            key = ticket["Ticket Key"]
            status = ticket["Status"]
            if key in client.key_to_id and status:
                log.info("Transitioning %s → %s", key, status)
                client.transition_issue(key, status)
    else:
        log.info("\n--- Skipping transitions (--skip-transitions) ---")

    # --- Step 6: Create issue links ---------------------------------------
    if not args.skip_links:
        log.info("\n--- Creating Issue Links ---")
        for ticket in tickets:
            source_key = ticket["Ticket Key"]
            links = parse_links(ticket.get("Links", ""))
            for link_info in links:
                keyword = link_info["keyword"]
                target_key = link_info["target"]

                link_def = LINK_TYPE_MAP.get(keyword)
                if not link_def:
                    log.warning("Unknown link keyword '%s' in %s → %s (skipped)",
                                keyword, source_key, target_key)
                    continue

                link_type_name = link_def["type"]
                direction = link_def["direction"]

                if direction == "outward":
                    # source is the outward issue
                    client.create_issue_link(link_type_name, target_key, source_key)
                else:
                    # source is the inward issue
                    client.create_issue_link(link_type_name, source_key, target_key)
    else:
        log.info("\n--- Skipping links (--skip-links) ---")

    # --- Summary ----------------------------------------------------------
    log.info("\n" + "=" * 60)
    log.info("UPLOAD COMPLETE")
    log.info("  Issues created:   %d / %d", len(created_keys), len(tickets))
    log.info("  Issues failed:    %d", len(failed_keys))
    log.info("  Dry-run:          %s", dry_run)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
