"""
mcp/context.py -- Layer 1: Context Store

Responsibility:
  * Load a project JSON file from disk into memory.
  * Validate the structure before passing downstream.
  * Expose the raw data and a human-readable "context window"
    (a structured text summary) that the Responder can include
    in prompts or logs.
  * Cache computed metrics once the Processor has run.

Nothing in this layer does any arithmetic or generates text answers.
It is purely a validated container and data-access interface.

Usage:
    ctx = ContextStore.load("flask")
    ctx = ContextStore.load("alpha")
    print(ctx.project_name)
    print(ctx.task_count)
    print(ctx.context_window())     # human-readable text summary
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

DATA_DIR     = Path(__file__).parent.parent / "data"
_SAFE_ID_RE  = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class ContextStore:
    """
    Holds all project data for one project.

    Attributes (set on load):
        project_id   : str
        project_name : str
        raw_data     : dict   -- the entire JSON as loaded
        metrics      : dict | None  -- set by Processor after analysis

    The ContextStore is intentionally dumb: it stores and exposes,
    it does not compute.
    """

    def __init__(self):
        self.project_id:   str        = ""
        self.project_name: str        = ""
        self.raw_data:     dict       = {}
        self.metrics:      Any | None = None
        self._source_path: Path | None = None

    # ── Factory method ─────────────────────────────────────────────────────────

    @classmethod
    def load(cls, project_id: str) -> "ContextStore":
        """
        Load a project from data/project_<project_id>.json.

        Raises:
            ValueError          on invalid project_id characters
            FileNotFoundError   if the file does not exist
            ValueError          on malformed JSON or missing required keys
        """
        if not _SAFE_ID_RE.match(project_id):
            raise ValueError(
                f"Unsafe project_id '{project_id}'. "
                "Only letters, digits, hyphens, and underscores are allowed."
            )

        path = DATA_DIR / f"project_{project_id}.json"
        if not path.exists():
            available = cls._available_ids()
            raise FileNotFoundError(
                f"No project file for id '{project_id}'.\n"
                f"Expected: {path}\n"
                f"Available: {available}"
            )

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error in {path.name}: {e}")

        # Structural validation
        for key in ("project", "tasks", "team"):
            if key not in raw:
                raise ValueError(
                    f"project_{project_id}.json missing required key '{key}'. "
                    f"Found: {list(raw.keys())}"
                )
        for key in ("name", "deadline"):
            if key not in raw["project"]:
                raise ValueError(
                    f"project.{key} is required but missing in {path.name}."
                )
        if not isinstance(raw["tasks"], list):
            raise ValueError(f"'tasks' must be a list in {path.name}.")
        if not isinstance(raw["team"], list):
            raise ValueError(f"'team' must be a list in {path.name}.")

        ctx = cls()
        ctx.project_id   = project_id
        ctx.project_name = raw["project"]["name"]
        ctx.raw_data     = raw
        ctx._source_path = path
        return ctx

    # ── Convenience accessors ──────────────────────────────────────────────────

    @property
    def project(self) -> dict:
        return self.raw_data["project"]

    @property
    def tasks(self) -> list:
        return self.raw_data["tasks"]

    @property
    def team(self) -> list:
        return self.raw_data["team"]

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def deadline(self) -> str:
        return self.project["deadline"]

    @property
    def is_processed(self) -> bool:
        """True once the Processor has populated self.metrics."""
        return self.metrics is not None

    @property
    def data_source(self) -> str:
        """Human-readable description of where this data comes from."""
        src = self.project.get("source", {})
        if src:
            src_type = src.get("type", "")

            if "jira" in src_type:
                domain  = src.get("domain", "")
                key     = src.get("project_key", "")
                fetched = src.get("fetched_at", "")
                return (
                    f"Jira Cloud ({domain}/jira/software/projects/{key}) "
                    f"-- live data fetched {fetched}"
                )

            if "github" in src_type:
                real  = src.get("real_issues", 0)
                synth = src.get("synth_issues", 0)
                url   = f"https://github.com/{src.get('owner','')}/{src.get('repo','')}"
                return (
                    f"GitHub Issues ({url}) "
                    f"-- {real} real API records + {synth} supplemental "
                    f"fetched {src.get('fetched_at','')}"
                )

        return "Local JSON file (simulated project data)"

    # ── Context window ─────────────────────────────────────────────────────────

    def context_window(self) -> str:
        """
        Return a human-readable text snapshot of the current project state.

        This is the "context" that would be injected into an LLM prompt
        in a real Model Context Protocol setup. Here it is used for
        logging, debugging, and the --context CLI flag.
        """
        t = self.tasks
        done    = sum(1 for x in t if x.get("status") == "Done")
        in_prog = sum(1 for x in t if x.get("status") == "In Progress")
        blocked = sum(1 for x in t if x.get("status") == "Blocked")
        todo    = sum(1 for x in t if x.get("status") == "To Do")
        total   = len(t)
        pct     = round(done / total * 100, 1) if total else 0.0

        team_names = [m.get("name","?") for m in self.team]

        lines = [
            f"PROJECT CONTEXT: {self.project_name}",
            f"Data source    : {self.data_source}",
            f"Deadline       : {self.deadline}",
            "",
            "Tasks:",
            f"  Total={total}  Done={done}  In-Progress={in_prog}  "
            f"Blocked={blocked}  To-Do={todo}  ({pct}% complete)",
            "",
            "Team:",
            f"  {', '.join(team_names)}",
            "",
            "Blocked tasks:",
        ]
        for task in t:
            if task.get("status") == "Blocked":
                lines.append(
                    f"  [{task.get('id','?')}] {task.get('title','')[:60]}"
                    f"  -- {task.get('assigned_to','?')}"
                    f"  ({task.get('estimated_time',0)}h estimated)"
                )

        if self.is_processed:
            m = self.metrics
            lines += [
                "",
                "Computed metrics (from Processor):",
                f"  Risk level         : {m.get('risk_level','')}",
                f"  Projected finish   : {m.get('projected_finish','')}",
                f"  Buffer days        : {m.get('buffer_days','')}",
                f"  Time variance      : {m.get('time_variance_pct','')}%",
                f"  Adjusted remaining : {m.get('adjusted_remaining_hours','')}h",
            ]

        return "\n".join(lines)

    # ── Listing helper ─────────────────────────────────────────────────────────

    @staticmethod
    def _available_ids() -> list[str]:
        ids = []
        for p in sorted(DATA_DIR.glob("project_*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                ids.append(d.get("project", {}).get("id", p.stem.replace("project_","")))
            except Exception:
                continue
        return ids

    @staticmethod
    def list_all() -> list[dict]:
        """Return [{id, name, file}] for all available projects."""
        projects = []
        for p in sorted(DATA_DIR.glob("project_*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                proj = d.get("project", {})
                projects.append({
                    "id":   proj.get("id", p.stem.replace("project_","")),
                    "name": proj.get("name", p.stem),
                    "file": p.name,
                })
            except Exception:
                continue
        return projects

    def __repr__(self) -> str:
        processed = "processed" if self.is_processed else "raw"
        return (f"<ContextStore id={self.project_id!r} "
                f"name={self.project_name!r} "
                f"tasks={self.task_count} {processed}>")
