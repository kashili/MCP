"""
connectors/ -- Live data connectors for the MCP pipeline.

Modules:
    jira_connector      Fetch issues from Jira Cloud REST API
    confluence_connector Fetch pages from Confluence Cloud REST API
    sync                Orchestrate both and save to data/ folder

Quick start:
    python connectors/sync.py          # Fetch + save everything
    python setup_check.py              # Verify credentials first
"""
