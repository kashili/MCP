"""
setup_check.py
==============
Run this BEFORE anything else to verify your credentials work.

    python setup_check.py

It will:
  1. Check your .env file exists
  2. Check all required variables are filled in
  3. Test the Jira API connection
  4. Test the Confluence API connection (if configured)
  5. Tell you exactly what to fix if anything is wrong

Green [PASS] = good.  Red [FAIL] = you need to fix this before continuing.
"""

import os
import sys
from pathlib import Path

# ── Make project imports work ──────────────────────────────────────────────────
_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

# ── Load .env ──────────────────────────────────────────────────────────────────
_ENV_FILE = _ROOT / ".env"
load_dotenv(_ENV_FILE)

WIDTH = 62
PASS  = "[PASS]"
FAIL  = "[FAIL]"
INFO  = "[INFO]"
WARN  = "[WARN]"


def _line(char="-"):
    print(char * WIDTH)


def ok(msg):
    print(f"  {PASS}  {msg}")
    return True


def fail(msg):
    print(f"  {FAIL}  {msg}")
    return False


def info(msg):
    print(f"  {INFO}  {msg}")


def warn(msg):
    print(f"  {WARN}  {msg}")


# ── Checks ─────────────────────────────────────────────────────────────────────

def check_env_file() -> bool:
    _line()
    print("CHECK 1: .env file")
    _line()
    if _ENV_FILE.exists():
        ok(f".env file found at: {_ENV_FILE}")
        return True
    else:
        fail(f".env file NOT found at: {_ENV_FILE}")
        print()
        print("  FIX: Copy the example file and fill it in:")
        print("       copy .env.example .env")
        print("       Then open .env in Notepad and fill in your values.")
        return False


def check_variables() -> bool:
    _line()
    print("CHECK 2: Required variables in .env")
    _line()

    DOMAIN      = os.getenv("ATLASSIAN_DOMAIN", "")
    EMAIL       = os.getenv("ATLASSIAN_EMAIL", "")
    TOKEN       = os.getenv("ATLASSIAN_API_TOKEN", "")
    PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "")

    all_ok = True

    if EMAIL and "@" in EMAIL and "example.com" not in EMAIL:
        ok(f"ATLASSIAN_EMAIL       = {EMAIL}")
    else:
        fail(f"ATLASSIAN_EMAIL       = '{EMAIL}'  (not filled in)")
        print("       FIX: Set ATLASSIAN_EMAIL to your real Atlassian login email.")
        all_ok = False

    if TOKEN and TOKEN != "your-api-token-here" and len(TOKEN) > 10:
        masked = TOKEN[:4] + "****" + TOKEN[-4:]
        ok(f"ATLASSIAN_API_TOKEN   = {masked}  (set)")
    else:
        fail(f"ATLASSIAN_API_TOKEN   = '{TOKEN}'  (not filled in)")
        print("       FIX: Get a token at: https://id.atlassian.com/manage-profile/security/api-tokens")
        all_ok = False

    if DOMAIN and "atlassian.net" in DOMAIN and "yourcompany" not in DOMAIN:
        ok(f"ATLASSIAN_DOMAIN      = {DOMAIN}")
    else:
        fail(f"ATLASSIAN_DOMAIN      = '{DOMAIN}'  (not filled in)")
        print("       FIX: Set to your real Jira URL, e.g. https://mycompany.atlassian.net")
        all_ok = False

    if PROJECT_KEY and PROJECT_KEY != "MYPROJ":
        ok(f"JIRA_PROJECT_KEY      = {PROJECT_KEY}")
    else:
        fail(f"JIRA_PROJECT_KEY      = '{PROJECT_KEY}'  (not filled in)")
        print("       FIX: Set to your project key, e.g. PROJ, MYAPP, DEV")
        print("            In Jira: open your project > Project Settings > Details > Key")
        all_ok = False

    # Optional variables
    print()
    DEADLINE   = os.getenv("JIRA_DEADLINE", "")
    SPACE_KEY  = os.getenv("CONFLUENCE_SPACE_KEY", "")
    HOURS      = os.getenv("JIRA_HOURS_PER_WEEK", "40")

    if DEADLINE:
        info(f"JIRA_DEADLINE         = {DEADLINE}  (optional, set)")
    else:
        info(f"JIRA_DEADLINE         = not set  (will use 90 days from today)")

    info(f"JIRA_HOURS_PER_WEEK   = {HOURS}")

    if SPACE_KEY:
        info(f"CONFLUENCE_SPACE_KEY  = {SPACE_KEY}  (Confluence will be synced)")
    else:
        info(f"CONFLUENCE_SPACE_KEY  = not set  (Confluence will be skipped)")

    return all_ok


def check_jira_connection() -> bool:
    _line()
    print("CHECK 3: Jira API connection")
    _line()

    DOMAIN      = os.getenv("ATLASSIAN_DOMAIN", "").rstrip("/")
    EMAIL       = os.getenv("ATLASSIAN_EMAIL", "")
    TOKEN       = os.getenv("ATLASSIAN_API_TOKEN", "")
    PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "").upper()

    if not all([DOMAIN, EMAIL, TOKEN, PROJECT_KEY]):
        warn("Skipping Jira connection test — variables not set.")
        return False

    auth = HTTPBasicAuth(EMAIL, TOKEN)
    hdrs = {"Accept": "application/json"}

    # Test 1: Can we reach the Jira API at all?
    try:
        r = requests.get(f"{DOMAIN}/rest/api/3/myself",
                         headers=hdrs, auth=auth, timeout=10)
    except requests.exceptions.ConnectionError:
        fail(f"Cannot connect to {DOMAIN}")
        print(f"       FIX: Check your internet connection.")
        print(f"            Check ATLASSIAN_DOMAIN is correct.")
        return False

    if r.status_code == 401:
        fail("401 Unauthorized — invalid credentials")
        print("       FIX: Check ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN in .env")
        print("            Generate a fresh token: https://id.atlassian.com/manage-profile/security/api-tokens")
        return False

    if r.status_code != 200:
        fail(f"Jira API returned HTTP {r.status_code}")
        return False

    me = r.json()
    ok(f"Connected to Jira as: {me.get('displayName', EMAIL)}")

    # Test 2: Can we access this specific project?
    try:
        r2 = requests.get(f"{DOMAIN}/rest/api/3/project/{PROJECT_KEY}",
                          headers=hdrs, auth=auth, timeout=10)
    except Exception as e:
        fail(f"Error fetching project: {e}")
        return False

    if r2.status_code == 404:
        fail(f"Project '{PROJECT_KEY}' not found")
        print(f"       FIX: Check JIRA_PROJECT_KEY in .env")
        print(f"            In Jira: Project Settings > Details > Key")
        return False

    if r2.status_code == 403:
        fail(f"Access denied to project '{PROJECT_KEY}'")
        print(f"       FIX: Make sure your account can view this project in Jira")
        return False

    if r2.status_code != 200:
        fail(f"Project API returned HTTP {r2.status_code}")
        return False

    proj = r2.json()
    ok(f"Project found: '{proj.get('name', PROJECT_KEY)}'  (key: {PROJECT_KEY})")

    # Test 3: Count issues
    try:
        r3 = requests.get(
            f"{DOMAIN}/rest/api/3/search",
            headers=hdrs, auth=auth, timeout=10,
            params={"jql": f"project = {PROJECT_KEY}", "maxResults": 1, "fields": "summary"},
        )
        total = r3.json().get("total", 0)
        ok(f"Issues accessible: {total} total")
    except Exception as e:
        warn(f"Could not count issues: {e}")

    return True


def check_confluence_connection() -> bool:
    _line()
    print("CHECK 4: Confluence API connection (optional)")
    _line()

    DOMAIN    = os.getenv("ATLASSIAN_DOMAIN", "").rstrip("/")
    EMAIL     = os.getenv("ATLASSIAN_EMAIL", "")
    TOKEN     = os.getenv("ATLASSIAN_API_TOKEN", "")
    SPACE_KEY = os.getenv("CONFLUENCE_SPACE_KEY", "").upper()

    if not SPACE_KEY:
        info("CONFLUENCE_SPACE_KEY not set — skipping Confluence check.")
        info("This is fine if you are not using Confluence.")
        return True

    if not all([DOMAIN, EMAIL, TOKEN]):
        warn("Cannot test Confluence — base credentials not set.")
        return False

    auth = HTTPBasicAuth(EMAIL, TOKEN)
    hdrs = {"Accept": "application/json"}

    try:
        r = requests.get(f"{DOMAIN}/wiki/rest/api/space/{SPACE_KEY}",
                         headers=hdrs, auth=auth, timeout=10)
    except requests.exceptions.ConnectionError:
        fail(f"Cannot connect to Confluence at {DOMAIN}/wiki/")
        return False

    if r.status_code == 401:
        fail("401 Unauthorized — check your API token")
        return False

    if r.status_code == 404:
        fail(f"Confluence space '{SPACE_KEY}' not found")
        print(f"       FIX: Check CONFLUENCE_SPACE_KEY in .env")
        print(f"            In Confluence: Space Settings > Space Details > Key")
        return False

    if r.status_code != 200:
        fail(f"Confluence API returned HTTP {r.status_code}")
        return False

    space = r.json()
    ok(f"Confluence space found: '{space.get('name', SPACE_KEY)}'")

    # Count pages
    try:
        r2 = requests.get(
            f"{DOMAIN}/wiki/rest/api/content",
            headers=hdrs, auth=auth, timeout=10,
            params={"spaceKey": SPACE_KEY, "type": "page", "limit": 1},
        )
        total = r2.json().get("size", 0)
        ok(f"Pages accessible: {total}")
    except Exception:
        pass

    return True


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    _line("=")
    print("  SETUP CHECK".center(WIDTH))
    print("  Verifying credentials before first sync".center(WIDTH))
    _line("=")
    print()

    results = []

    env_ok   = check_env_file()
    print()
    results.append(("  .env file exists",   env_ok))

    if not env_ok:
        print("Fix the .env file first, then re-run: python setup_check.py\n")
        sys.exit(1)

    vars_ok  = check_variables()
    print()
    results.append(("  Required variables",  vars_ok))

    jira_ok  = check_jira_connection()
    print()
    results.append(("  Jira API",            jira_ok))

    conf_ok  = check_confluence_connection()
    print()
    results.append(("  Confluence API",      conf_ok))

    # ── Final summary ──────────────────────────────────────────────────────────
    _line("=")
    print("  SUMMARY".center(WIDTH))
    _line("=")
    all_critical_ok = True
    for name, passed in results:
        status = PASS if passed else FAIL
        print(f"  {status}  {name}")
        if not passed and "Confluence" not in name:
            all_critical_ok = False
    _line()
    print()

    if all_critical_ok:
        print("  All required checks passed!")
        print()
        print("  Next step -- fetch your Jira data:")
        print()
        print("      python connectors/sync.py")
        print()
    else:
        print("  Fix the FAIL items above, then re-run:")
        print("      python setup_check.py")
        print()

    _line("=")


if __name__ == "__main__":
    main()
