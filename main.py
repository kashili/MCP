"""
main.py -- ATM-style CLI using the 3-layer MCP pipeline.

MCP Pipeline (executed on every question):
  Layer 1  mcp.context.ContextStore.load(project_id)
              Reads data/project_<id>.json from disk.
              Validates structure. Builds context window.

  Layer 2  mcp.processor.Processor().process(context)
              Analyses raw data: completion, risk, timeline,
              resource allocation, priorities.
              Stores metrics in context.metrics.

  Layer 3  mcp.responder.Responder().answer(question, context)
              Routes question by keyword tier.
              Builds structured plain-text answer from metrics.
              Never invents or guesses any value.

Usage:
    python main.py                      # interactive mode
    python main.py --demo               # auto-run 5 questions on every project
    python main.py --project flask      # open specific project
    python main.py --context flask      # print context window and exit
"""

import sys
import textwrap

from mcp.context   import ContextStore
from mcp.processor import Processor
from mcp.responder import Responder

WIDTH = 64

DEMO_QUESTIONS = [
    "Give me a full project overview",
    "When will this project be completed?",
    "What are the main risks?",
    "Are there any blocked tasks?",
    "What should the team focus on next?",
]

_processor = Processor()
_responder = Responder()


# ── Display helpers ────────────────────────────────────────────────────────────

def _line(char="-"):
    print(char * WIDTH)

def _header():
    _line("=")
    print("  LOCAL LLM PROJECT MANAGER  [MCP Architecture]".center(WIDTH))
    print("  Context -> Processor -> Responder  |  Fully offline".center(WIDTH))
    _line("=")
    print()

def _project_snapshot(ctx: ContextStore):
    m   = ctx.metrics
    pct = m["completion_pct"]
    bar = "#" * round(pct / 100 * 28) + "-" * (28 - round(pct / 100 * 28))
    _line()
    print(f"  PROJECT  : {m['project_name']}")
    print(f"  SOURCE   : {m['data_source']}")
    print(f"  RISK     : {m['risk_level']:<10}  BUFFER : {m['buffer_days']} days")
    print(f"  PROGRESS : [{bar}] {pct}%")
    print(f"  STATUS   : {'On Track' if m['on_track'] else 'BEHIND SCHEDULE'}")
    print(
        f"  TASKS    : {m['tasks_done']} done  "
        f"{m['tasks_in_progress']} in-progress  "
        f"{m['tasks_blocked']} blocked  "
        f"{m['tasks_todo']} to-do  "
        f"(total {m['tasks_total']})"
    )
    print(f"  FINISH   : {m['projected_finish']}  (deadline {m['deadline']})")
    _line()
    print()

def _print_answer(answer: str):
    _line()
    for raw in answer.splitlines():
        print(raw if len(raw) <= WIDTH else textwrap.fill(
            raw, width=WIDTH, subsequent_indent="    "))
    _line()
    print()

def _project_menu(projects: list) -> str:
    print("  Available Projects:")
    print()
    for i, p in enumerate(projects, 1):
        print(f"    {i}.  {p['name']}  [{p['id']}]")
    print()
    ids = [p["id"] for p in projects]
    while True:
        choice = input("  Select [number or id]: ").strip()
        if choice.isdigit() and 0 <= int(choice)-1 < len(projects):
            return projects[int(choice)-1]["id"]
        if choice in ids:
            return choice
        print(f"  Invalid. Enter 1-{len(projects)} or one of {ids}.")

def _help_text():
    _line()
    print("  HELP -- MCP pipeline query examples")
    print()
    print("  Natural language questions:")
    print("    Give me a project overview")
    print("    When will this project be completed?")
    print("    What are the main risks?")
    print("    Are there any blocked tasks?")
    print("    Who is overloaded on the team?")
    print("    What should we focus on next?")
    print()
    print("  Commands:")
    print("    switch   -- select different project")
    print("    sync     -- fetch fresh data from Jira (needs .env)")
    print("    context  -- show MCP context window")
    print("    demo     -- run 5 example questions")
    print("    snapshot -- show status card")
    print("    help     -- this screen")
    print("    quit     -- exit")
    _line()
    print()


# ── MCP load + process (used everywhere) ──────────────────────────────────────

def _load_and_process(project_id: str) -> ContextStore:
    """
    Execute MCP Layers 1 and 2.
    Layer 1: ContextStore.load() reads JSON from disk
    Layer 2: Processor.process() computes all metrics
    """
    ctx = ContextStore.load(project_id)     # Layer 1
    ctx = _processor.process(ctx)           # Layer 2
    return ctx


# ── Demo runner ────────────────────────────────────────────────────────────────

def _run_demo(ctx: ContextStore):
    m = ctx.metrics
    print(f"  Demo -- {m['project_name']}\n")
    for i, q in enumerate(DEMO_QUESTIONS, 1):
        print(f"  [{i}/{len(DEMO_QUESTIONS)}] Q: {q}")
        answer = _responder.answer(q, ctx)  # Layer 3
        _print_answer(answer)
        if i < len(DEMO_QUESTIONS):
            input("  [Enter] for next question...")
    print(f"  Demo complete.\n")


# ── Interactive session ────────────────────────────────────────────────────────

def _interactive_loop(initial_id, projects: list):
    if not projects:
        print("  ERROR: No project files found in data/.")
        print("  Add data/project_<id>.json or run data/build_project.py")
        return

    if initial_id and any(p["id"] == initial_id for p in projects):
        project_id = initial_id
    else:
        if initial_id:
            print(f"  Project '{initial_id}' not found.\n")
        project_id = _project_menu(projects)

    while True:
        # ── MCP Layers 1+2 ────────────────────────────────────────────────────
        try:
            ctx = _load_and_process(project_id)
        except (FileNotFoundError, ValueError) as e:
            print(f"\n  ERROR: {e}\n")
            project_id = _project_menu(projects)
            continue

        _project_snapshot(ctx)
        print("  Ask a question or command  (type 'help'):\n")

        while True:
            try:
                raw = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Goodbye!\n")
                return

            if not raw:
                continue

            cmd = raw.lower()

            if cmd in ("quit", "exit", "q"):
                print("\n  Goodbye!\n")
                return

            if cmd in ("switch", "sw", "s"):
                print()
                project_id = _project_menu(projects)
                break   # reload outer loop

            if cmd == "sync":
                print("\n  Fetching live data from Jira ...\n")
                try:
                    from connectors.sync import run_sync
                    result = run_sync(verbose=True)
                    projects   = ContextStore.list_all()   # refresh list
                    project_id = result["project_id"]
                except SystemExit:
                    print("\n  Sync cancelled. Check .env and run: python setup_check.py\n")
                except Exception as e:
                    print(f"\n  Sync error: {e}\n")
                break   # reload outer loop with new project

            if cmd in ("demo", "d"):
                _run_demo(ctx)
                continue

            if cmd in ("context", "ctx"):
                _line()
                print(ctx.context_window())  # Layer 1 context window
                _line()
                print()
                continue

            if cmd in ("snapshot", "snap", "status"):
                _project_snapshot(ctx)
                continue

            if cmd in ("help", "h", "?"):
                _help_text()
                continue

            # ── MCP Layer 3: Responder answers the question ────────────────────
            print()
            answer = _responder.answer(raw, ctx)
            _print_answer(answer)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    _header()

    projects = ContextStore.list_all()
    args     = sys.argv[1:]

    # --context <id>: print context window and exit
    if "--context" in args:
        idx = args.index("--context")
        pid = args[idx + 1] if idx + 1 < len(args) else (projects[0]["id"] if projects else "")
        if pid:
            try:
                ctx = _load_and_process(pid)
                _line()
                print(ctx.context_window())
                _line()
            except Exception as e:
                print(f"  ERROR: {e}")
        return

    # --demo: run 5 questions on every project, non-interactive
    if "--demo" in args:
        if not projects:
            print("  No project files found.\n")
            return
        for p in projects:
            try:
                ctx = _load_and_process(p["id"])
                _project_snapshot(ctx)
                _run_demo(ctx)
            except Exception as e:
                print(f"  ERROR loading {p['id']}: {e}\n")
        return

    # --project <id>: start on specific project
    initial_id = None
    if "--project" in args:
        idx = args.index("--project")
        if idx + 1 < len(args):
            initial_id = args[idx + 1]

    _interactive_loop(initial_id, projects)


if __name__ == "__main__":
    main()
