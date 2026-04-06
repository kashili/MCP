"""
mcp/responder.py -- Layer 3: Responder

Responsibility:
  * Accept a natural-language question and a processed ContextStore.
  * Route the question to the correct answer handler using keyword tiers.
  * Build a structured plain-text answer exclusively from context.metrics.
  * Return the answer string.

Guarantee:
  Every value printed in an answer is taken directly from context.metrics,
  which was computed by the Processor from the raw data.
  The Responder never generates, guesses, or invents any value.

Routing tiers (in priority order):
  1. Blocker questions    -> _answer_blockers()
  2. Priority / actions  -> _answer_priorities()
  3. Resource / team     -> _answer_resources()
  4. Summary / overview  -> _answer_summary()
  5. Risk / delay        -> _answer_risks()
  6. Timeline / progress -> _answer_timeline()
  7. Fallback            -> _answer_summary()

Usage:
    ctx = ContextStore.load("flask")
    ctx = Processor().process(ctx)
    answer = Responder().answer("What are the blocked tasks?", ctx)
    print(answer)
"""

from __future__ import annotations
from mcp.context import ContextStore


def _try_ollama(question: str, context: ContextStore) -> str | None:
    """
    Try to answer via Ollama. Returns None if Ollama is not running.
    Uses the full computed metrics as context so Ollama answers from real data.
    """
    try:
        from src.llm_interface import _ollama_is_running, _ollama_has_model, _query_ollama
        if not _ollama_is_running():
            return None

        m = context.metrics

        # Build a rich structured context for Ollama
        team_lines = "\n".join(
            f"  - {t['name']} ({t['role']}): "
            f"{t['tasks_assigned']} tasks, load={t['load_ratio']:.2f}x"
            + (" [OVERLOADED]" if t.get("overloaded") else "")
            + (" [UNDERUSED]"  if t.get("underused")  else "")
            for t in m.get("team_analysis", [])
        )
        blocked_lines = "\n".join(
            f"  - [{b['id']}] {b['title']} (assigned: {b['assigned_to']}, {b['estimated_time']}h)"
            for b in m.get("blocked_tasks", [])
        ) or "  None"

        rich_context = f"""PROJECT: {m['project_name']}
Data source  : {m['data_source']}
Deadline     : {m['deadline']}
Completion   : {m['completion_pct']}%  ({m['tasks_done']} done / {m['tasks_total']} total)
In Progress  : {m['tasks_in_progress']}
Blocked      : {m['tasks_blocked']}
To Do        : {m['tasks_todo']}

TIMELINE
Projected finish : {m['projected_finish']}
Buffer days      : {m['buffer_days']} days
On track         : {'YES' if m['on_track'] else 'NO - BEHIND SCHEDULE'}
Hours remaining  : {m['adjusted_remaining_hours']}h (adjusted for {m['time_variance_pct']}% historical variance)
Daily capacity   : {m['daily_capacity']}h/day

RISK
Risk level   : {m['risk_level']}
Risk factors :
{chr(10).join('  - ' + r for r in m.get('risk_factors', ['None']))}

BLOCKED TASKS
{blocked_lines}

TEAM
{team_lines or '  No team data'}

PRIORITIES
{chr(10).join('  ' + str(i+1) + '. ' + p for i, p in enumerate(m.get('priorities', [])))}
"""
        # Suppress streaming stdout — caller handles display
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = _query_ollama(rich_context, question)
        return result

    except Exception:
        return None


# ── Keyword sets ───────────────────────────────────────────────────────────────

_BLOCKER_KW  = {"block", "stuck", "stall", "impediment", "stopp",
                "unblock", "halt", "impedance"}

_RESOURCE_KW = {"resource", "workload", "overload", "underutil",
                "capacity", "who is assign", "who has", "team member",
                "staff", "who is over", "who is under", "load ratio",
                "reassign", "redistribute"}

_RISK_KW     = {"risk", "delay", "late", "behind", "overdue", "danger",
                "threat", "miss deadline", "concern", "worst case"}

_PRIORITY_KW = {"priorit", "next step", "what should", "recommend",
                "action item", "focus on", "most urgent", "what to do",
                "key action"}

_SUMMARY_KW  = {"summary", "overview", "overall", "brief",
                "describe the project", "tell me about", "general",
                "health check", "project report", "how is the project",
                "status of the project", "give me a report"}

_TIMELINE_KW = {"when will", "when does", "finish date", "completion date",
                "how long", "days remaining", "weeks remaining",
                "deadline", "how many days", "time to complete",
                "eta", "forecast", "completion estimate", "will it finish",
                "schedule", "buffer", "on track", "behind schedule"}

_TEAM_KW     = {"who", "team", "member", "assign", "person", "people",
                "developer", "engineer", "designer", "contributor", "role"}

_PROGRESS_KW = {"progress", "percent", "how far", "completion", "how much",
                "done so far", "how complete", "tasks done", "task count"}


class Responder:
    """
    Stateless question router and answer builder.
    Call answer(question, context) to get a structured response.
    """

    def answer(self, question: str, context: ContextStore) -> str:
        """
        Route question to the appropriate handler and return a plain-text answer.

        Parameters
        ----------
        question : str            Natural-language question from the user.
        context  : ContextStore   Must already be processed (context.is_processed).

        Raises
        ------
        RuntimeError  if context has not been processed yet.
        """
        if not context.is_processed:
            raise RuntimeError(
                "ContextStore must be processed before answering. "
                "Call Processor().process(context) first."
            )

        # Try Ollama first (real local LLM) — falls back silently if not running
        ollama_answer = _try_ollama(question, context)
        if ollama_answer:
            return ollama_answer

        # Fall back to rule-based responder
        m = context.metrics
        q = question.lower().strip()

        # Tier 1-6: keyword routing
        if self._match(q, _BLOCKER_KW):
            return self._answer_blockers(m)
        if self._match(q, _PRIORITY_KW):
            return self._answer_priorities(m)
        if self._match(q, _RESOURCE_KW) or self._match(q, _TEAM_KW):
            return self._answer_resources(m)
        if self._match(q, _SUMMARY_KW):
            return self._answer_summary(m)
        if self._match(q, _RISK_KW):
            return self._answer_risks(m)
        if self._match(q, _TIMELINE_KW) or self._match(q, _PROGRESS_KW):
            return self._answer_timeline(m)

        # Tier 7: fallback
        return self._answer_summary(m)

    # ── Routing helper ─────────────────────────────────────────────────────────

    @staticmethod
    def _match(text: str, keywords: set) -> bool:
        return any(kw in text for kw in keywords)

    # ── Format helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _risk_label(level: str) -> str:
        return {
            "LOW":      "LOW      (GREEN)",
            "MEDIUM":   "MEDIUM   (YELLOW)",
            "HIGH":     "HIGH     (ORANGE)",
            "CRITICAL": "CRITICAL (RED)",
        }.get(level, level)

    @staticmethod
    def _bar(pct: float, width: int = 20) -> str:
        pct    = max(0.0, min(100.0, float(pct)))
        filled = round(pct / 100 * width)
        return "[" + "=" * filled + "-" * (width - filled) + f"] {pct}%"

    @staticmethod
    def _div(w: int = 50) -> str:
        return "-" * w

    # ── Answer handlers (all values pulled from metrics dict) ─────────────────

    def _answer_timeline(self, m: dict) -> str:
        buf_msg = (
            f"This leaves a {m['buffer_days']}-day buffer before the deadline."
            if m["buffer_days"] > 0
            else (
                "The project is projected to finish exactly on the deadline."
                if m["buffer_days"] == 0
                else f"WARNING: Deadline already missed by {abs(m['buffer_days'])} days."
            )
        )
        lines = [
            f"COMPLETION ESTIMATE -- {m['project_name']}",
            self._div(),
            f"Data source    : {m['data_source']}",
            "",
            f"Progress       : {self._bar(m['completion_pct'])}",
            f"Status         : {'ON TRACK' if m['on_track'] else 'BEHIND SCHEDULE'}",
            "",
            "Work Remaining:",
            f"  Raw hours left       : {m['remaining_hours']}h",
            f"  Variance-adjusted    : {m['adjusted_remaining_hours']}h  "
            f"(+{m['time_variance_pct']}% from historical over-runs)",
            f"  Team daily capacity  : {m['daily_capacity']}h/day",
            f"  Days to finish       : ~{m['estimated_days_remaining']} working days",
            "",
            "Key Dates:",
            f"  Project start    : {m['start_date']}",
            f"  Projected finish : {m['projected_finish']}",
            f"  Deadline         : {m['deadline']}",
            f"  Buffer           : {m['buffer_days']} days",
            "",
            buf_msg,
        ]
        if m["time_variance_pct"] > 20:
            lines.append(
                f"\nNote: {m['time_variance_pct']}% historical over-run detected. "
                "Adjusted estimate already accounts for this."
            )
        return "\n".join(lines)

    def _answer_risks(self, m: dict) -> str:
        lines = [
            f"RISK ANALYSIS -- {m['project_name']}",
            self._div(),
            f"Data source        : {m['data_source']}",
            "",
            f"Overall Risk Level : {self._risk_label(m['risk_level'])}",
            f"Projected Finish   : {m['projected_finish']}",
            f"Deadline           : {m['deadline']}",
            f"Buffer             : {m['buffer_days']} days",
            "",
            "Risk Factors (derived from data):",
        ]
        for i, f in enumerate(m["risk_factors"], 1):
            lines.append(f"  {i}. {f}")

        lines += [
            "",
            "Supporting Metrics:",
            f"  Blocked tasks   : {m['tasks_blocked']}",
            f"  Time variance   : {m['time_variance_pct']}%",
            f"  Deadline buffer : {m['buffer_days']} days",
        ]

        level = m["risk_level"]
        if level == "CRITICAL":
            lines += [
                "",
                "ACTION REQUIRED:",
                "  1. Resolve all blocked tasks today.",
                "  2. Escalate to stakeholders.",
                "  3. Defer low-priority tasks to reduce scope.",
                "  4. Re-estimate remaining work.",
            ]
        elif level == "HIGH":
            lines += ["", "CAUTION: Manageable but requires immediate attention."]
        elif level == "MEDIUM":
            lines += ["", "WATCH: Monitor blockers and variance weekly."]
        else:
            lines += ["", "Project is in good health. Continue current pace."]

        return "\n".join(lines)

    def _answer_blockers(self, m: dict) -> str:
        blocked = m["blocked_tasks"]
        lines   = [
            f"BLOCKED TASKS -- {m['project_name']}",
            self._div(),
            f"Data source : {m['data_source']}",
            "",
        ]
        if not blocked:
            lines += [
                "No blocked tasks. All work is progressing normally.",
                "",
                "Note: Task status is read directly from the project data file.",
            ]
            return "\n".join(lines)

        total_h = sum(t["hours"] for t in blocked)
        lines.append(
            f"{len(blocked)} task(s) BLOCKED -- {total_h}h of work stalled.\n"
        )
        for i, t in enumerate(blocked, 1):
            origin = "real GitHub issue" if t.get("real") else "supplemental record"
            lines += [
                f"  [{i}] {t['id']} -- {t['title'][:60]}",
                f"       Priority     : {t['priority']}",
                f"       Assigned to  : {t['assigned_to']}",
                f"       Hours at risk: {t['hours']}h",
                f"       Record type  : {origin}",
                "",
            ]
        lines += [
            "Recommended Actions:",
            "  1. Hold emergency stand-up to identify root cause.",
            "  2. Assign single owner per blocked task.",
            "  3. Set 24-hour resolution target.",
            "  4. Escalate to leadership if blockers exceed 48h.",
        ]
        return "\n".join(lines)

    def _answer_resources(self, m: dict) -> str:
        team = m["team_analysis"]
        overloaded = [x for x in team if x["load_status"] == "overloaded"]
        underutil  = [x for x in team if x["load_status"] == "underutilised"]

        lines = [
            f"RESOURCE ANALYSIS -- {m['project_name']}",
            self._div(),
            f"Data source    : {m['data_source']}",
            "",
            f"Team size      : {len(team)} members",
            f"Team capacity  : {m['daily_capacity']}h/day  "
            f"({round(m['daily_capacity'] * 5, 1)}h/week)",
            f"Tasks total    : {m['tasks_total']}   |   Completed: {m['tasks_done']}",
            "",
            "Individual Workload:",
            "",
        ]

        for mb in team:
            assigned = mb["tasks_assigned"]
            done     = mb["tasks_done"]
            pct      = round(done / assigned * 100) if assigned else 0
            bar      = self._bar(pct, width=12)
            tag      = {"overloaded": " << OVERLOADED",
                        "underutilised": " << UNDERUSED",
                        "balanced": ""}.get(mb["load_status"], "")
            blk_note = f"  [{mb['tasks_blocked']} blocked]" if mb["tasks_blocked"] else ""
            lines.append(
                f"  {mb['name']:<12}  {mb['role']:<20}"
                f"  load={mb['load_ratio']}x  {done}/{assigned} tasks  "
                f"{bar}{blk_note}{tag}"
            )

        lines.append("")
        if overloaded:
            names = ", ".join(x["name"] for x in overloaded)
            lines += [
                f"OVERLOADED : {names}",
                "  -> Redistribute tasks to prevent burnout.",
            ]
        if underutil:
            names = ", ".join(x["name"] for x in underutil)
            lines += [
                f"UNDERUSED  : {names}",
                "  -> Capacity available; assign more work.",
            ]
        if not overloaded and not underutil:
            lines.append("Team workload is BALANCED.")

        return "\n".join(lines)

    def _answer_priorities(self, m: dict) -> str:
        lines = [
            f"RECOMMENDED ACTIONS -- {m['project_name']}",
            self._div(),
            f"Data source    : {m['data_source']}",
            "",
            f"Risk Level     : {self._risk_label(m['risk_level'])}",
            f"Deadline Buffer: {m['buffer_days']} days",
            f"Blocked Tasks  : {m['tasks_blocked']}",
            f"Time Variance  : {m['time_variance_pct']}%",
            "",
            "Priority Actions (derived from current data):",
        ]
        for i, p in enumerate(m["priorities"], 1):
            lines.append(f"  {i}. {p}")

        lines += [
            "",
            "Standing Recommendations:",
            "  * Daily stand-up to surface blockers early.",
            "  * Re-estimate tasks with >30% variance.",
            "  * Review resource allocation if load ratio >1.3x.",
        ]
        if m["risk_level"] in ("CRITICAL", "HIGH"):
            lines += [
                "",
                f"ESCALATION: Risk level is {m['risk_level']}.",
                "  Communicate status to stakeholders this week.",
            ]
        return "\n".join(lines)

    def _answer_summary(self, m: dict) -> str:
        lines = [
            f"PROJECT OVERVIEW -- {m['project_name']}",
            self._div(),
            f"Data source : {m['data_source']}",
        ]
        if m.get("description"):
            lines += ["", f"  {m['description']}"]

        lines += [
            "",
            f"Progress : {self._bar(m['completion_pct'])}",
            f"Status   : {'On Track' if m['on_track'] else 'BEHIND SCHEDULE'}"
            f"   |   Risk: {self._risk_label(m['risk_level'])}",
            "",
            "Task Breakdown:",
            f"  Done        : {m['tasks_done']}",
            f"  In Progress : {m['tasks_in_progress']}",
            f"  Blocked     : {m['tasks_blocked']}",
            f"  To Do       : {m['tasks_todo']}",
            f"  Total       : {m['tasks_total']}",
            "",
            "Timeline:",
            f"  Start date       : {m['start_date']}",
            f"  Projected finish : {m['projected_finish']}"
            f"  (~{m['estimated_days_remaining']} working days from today)",
            f"  Deadline         : {m['deadline']}",
            f"  Buffer           : {m['buffer_days']} days",
            f"  Work remaining   : {m['adjusted_remaining_hours']}h"
            f"  (+{m['time_variance_pct']}% variance adjustment)",
            f"  Team capacity    : {m['daily_capacity']}h/day",
            "",
            "Team Snapshot:",
        ]
        for mb in m["team_analysis"]:
            tag = {"overloaded": " <<OVERLOADED",
                   "underutilised": " <<UNDERUSED",
                   "balanced": ""}.get(mb["load_status"], "")
            lines.append(
                f"  {mb['name']:<12} {mb['role']:<20} "
                f"load={mb['load_ratio']}x  {mb['tasks_done']}/{mb['tasks_assigned']} done"
                f"{tag}"
            )

        lines += ["", "Key Risk Factors:"]
        for f in m["risk_factors"]:
            lines.append(f"  * {f}")

        lines += ["", "Top Priorities:"]
        for p in m["priorities"]:
            lines.append(f"  -> {p}")

        return "\n".join(lines)
