"""
mcp/processor.py -- Layer 2: Processor

Responsibility:
  * Accept a ContextStore from Layer 1.
  * Run all analytical computations on the raw data.
  * Store computed metrics back into context.metrics.
  * Return the updated ContextStore so Layer 3 can use it.

Computations performed (all arithmetic, no text generation):
  - Task breakdown counts (done / in-progress / blocked / to-do)
  - Completion percentage
  - Time variance from completed tasks (actual vs estimated)
  - Remaining hours (raw and variance-adjusted)
  - Daily team capacity
  - Days to finish, projected finish date, deadline buffer
  - Risk level (LOW / MEDIUM / HIGH / CRITICAL)
  - Per-member load ratio and load status
  - Blocked task details
  - Risk factors and priority recommendations (as data, not prose)

Isolation guarantee:
  The Processor only reads from context.raw_data.
  It never reads from the filesystem or any network.
  Every output value is a direct arithmetic result of input data.

Usage:
    ctx = ContextStore.load("flask")
    ctx = Processor().process(ctx)
    print(ctx.metrics["risk_level"])
"""

from __future__ import annotations
from datetime import date, datetime, timedelta
from mcp.context import ContextStore

TODAY     = date.today()
_MAX_DAYS = 9999


class Processor:
    """
    Stateless analyser.  Call process(context) to populate context.metrics.

    All computations are reproducible: same input data always produces
    the same output metrics.
    """

    def process(self, context: ContextStore) -> ContextStore:
        """
        Analyse the data in context.raw_data and populate context.metrics.

        Parameters
        ----------
        context : ContextStore  (from Layer 1, not yet processed)

        Returns
        -------
        The same ContextStore with context.metrics populated.

        Raises
        ------
        ValueError  if deadline is not in YYYY-MM-DD format
        """
        data    = context.raw_data
        project = data["project"]
        tasks   = data["tasks"]
        team    = data["team"]

        # ── 1. Task breakdown ─────────────────────────────────────────────────
        done    = [t for t in tasks if t.get("status") == "Done"]
        in_prog = [t for t in tasks if t.get("status") == "In Progress"]
        blocked = [t for t in tasks if t.get("status") == "Blocked"]
        todo    = [t for t in tasks if t.get("status") == "To Do"]
        total   = len(tasks)
        pct     = round(len(done) / total * 100, 1) if total else 0.0

        # ── 2. Time variance (completed tasks only) ───────────────────────────
        variances = []
        for t in done:
            est = t.get("estimated_time") or 0
            act = t.get("actual_time")          # may be None
            if est > 0 and act is not None and act > 0:
                variances.append((act - est) / est)
        avg_var = sum(variances) / len(variances) if variances else 0.0
        avg_var = max(-0.9, avg_var)   # floor: can't save more than 90%

        # ── 3. Remaining hours ────────────────────────────────────────────────
        remaining = sum(
            max(0.0, (t.get("estimated_time") or 0) - (t.get("actual_time") or 0))
            for t in in_prog + blocked + todo
        )
        adjusted = max(0.0, remaining * (1 + avg_var))

        # ── 4. Team capacity (hours/day) ──────────────────────────────────────
        daily_cap = sum(m.get("capacity_hours_per_week", 40) / 5 for m in team)

        # ── 5. Timeline forecast ──────────────────────────────────────────────
        days_left = adjusted / daily_cap if daily_cap > 0 else float(_MAX_DAYS)
        proj_fin  = TODAY + timedelta(days=round(days_left))

        try:
            deadline = datetime.strptime(project["deadline"], "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(
                f"deadline '{project['deadline']}' must be YYYY-MM-DD format."
            )

        buf      = (deadline - proj_fin).days
        on_track = proj_fin <= deadline

        # ── 6. Risk level ─────────────────────────────────────────────────────
        n_blocked = len(blocked)
        if buf < 0 or n_blocked >= 3:
            risk = "CRITICAL"
        elif n_blocked >= 1 or buf < 7 or avg_var > 0.25:
            risk = "HIGH"
        elif avg_var > 0.10 or buf < 21:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        # ── 7. Resource analysis ──────────────────────────────────────────────
        task_map     = {t["id"]: t for t in tasks}
        total_est    = sum(t.get("estimated_time", 0) for t in tasks)
        avg_per_head = total_est / len(team) if team else 0.0

        team_analysis = []
        for member in team:
            ids           = member.get("assigned_tasks", [])
            mbr_tasks     = [task_map[i] for i in ids if i in task_map]
            mbr_hours     = sum(t.get("estimated_time", 0) for t in mbr_tasks)
            mbr_done      = sum(1 for t in mbr_tasks if t.get("status") == "Done")
            mbr_blocked   = sum(1 for t in mbr_tasks if t.get("status") == "Blocked")
            load_ratio    = round(mbr_hours / avg_per_head, 2) if avg_per_head > 0 else 1.0

            if load_ratio > 1.4:
                load_status = "overloaded"
            elif load_ratio < 0.6:
                load_status = "underutilised"
            else:
                load_status = "balanced"

            team_analysis.append({
                "name":              member.get("name", "Unknown"),
                "role":              member.get("role", "Contributor"),
                "tasks_assigned":    len(mbr_tasks),
                "tasks_done":        mbr_done,
                "tasks_blocked":     mbr_blocked,
                "estimated_hours":   mbr_hours,
                "capacity_per_week": member.get("capacity_hours_per_week", 40),
                "load_ratio":        load_ratio,
                "load_status":       load_status,
            })

        # ── 8. Blocked task details ───────────────────────────────────────────
        blocked_details = [
            {
                "id":          t.get("id", "?"),
                "title":       t.get("title", "Untitled"),
                "assigned_to": t.get("assigned_to", "Unassigned"),
                "hours":       t.get("estimated_time", 0),
                "priority":    t.get("priority", "Medium"),
                "real":        t.get("_real", None),   # track data origin
            }
            for t in blocked
        ]

        # ── 9. Risk factors (structured data, not generated text) ─────────────
        risk_factors = []
        if blocked:
            hrs = sum(t.get("estimated_time", 0) for t in blocked)
            risk_factors.append(
                f"{len(blocked)} task(s) blocked -- {hrs}h of work stalled"
            )
        if avg_var > 0.10:
            risk_factors.append(
                f"Tasks running {round(avg_var * 100)}% over original estimates on average"
            )
        if buf < 0:
            risk_factors.append(
                f"Deadline already missed -- {abs(buf)} days overdue"
            )
        elif buf < 14:
            risk_factors.append(
                f"Deadline buffer critically low -- only {buf} days remaining"
            )
        overloaded = [m for m in team_analysis if m["load_status"] == "overloaded"]
        for mb in overloaded:
            risk_factors.append(
                f"{mb['name']} is overloaded ({mb['tasks_assigned']} tasks, "
                f"load ratio {mb['load_ratio']}x average)"
            )
        if not risk_factors:
            risk_factors.append("No major risk factors detected -- project is healthy")

        # ── 10. Priority recommendations ──────────────────────────────────────
        priorities = []
        if blocked:
            priorities.append(
                f"Unblock {len(blocked)} stalled task(s) -- "
                f"{sum(t['hours'] for t in blocked_details)}h at stake"
            )
        if overloaded:
            priorities.append(
                f"Redistribute tasks from {overloaded[0]['name']} "
                f"(load ratio: {overloaded[0]['load_ratio']}x)"
            )
        underutil = [m for m in team_analysis if m["load_status"] == "underutilised"]
        if underutil:
            priorities.append(
                f"Assign more work to {underutil[0]['name']} "
                f"({underutil[0]['capacity_per_week']}h/wk capacity underused)"
            )
        if avg_var > 0.15:
            priorities.append(
                "Review task estimates -- consistent overruns detected"
            )
        if not priorities:
            priorities.append("Maintain current pace and monitor velocity weekly")

        # ── Store metrics in context ───────────────────────────────────────────
        context.metrics = {
            "project_id":               project.get("id", ""),
            "project_name":             project["name"],
            "description":              project.get("description", ""),
            "start_date":               project.get("start_date", "N/A"),
            "deadline":                 project["deadline"],
            "data_source":              context.data_source,
            # Task counts
            "tasks_total":              total,
            "tasks_done":               len(done),
            "tasks_in_progress":        len(in_prog),
            "tasks_blocked":            len(blocked),
            "tasks_todo":               len(todo),
            "completion_pct":           pct,
            # Hours
            "remaining_hours":          round(remaining, 1),
            "adjusted_remaining_hours": round(adjusted, 1),
            "time_variance_pct":        round(avg_var * 100, 1),
            # Timeline
            "daily_capacity":           round(daily_cap, 1),
            "estimated_days_remaining": round(days_left, 1),
            "projected_finish":         str(proj_fin),
            "buffer_days":              buf,
            "on_track":                 on_track,
            # Risk
            "risk_level":               risk,
            "risk_factors":             risk_factors,
            # Team
            "team_analysis":            team_analysis,
            # Details
            "blocked_tasks":            blocked_details,
            "priorities":               priorities,
        }

        return context
