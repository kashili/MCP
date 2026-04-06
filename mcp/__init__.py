"""
mcp/ -- Model-Context-Processing architecture for the LLM Project Manager.

Three-layer pipeline:

  Layer 1 -- Context  (mcp/context.py)
    Responsibility : Load data, validate it, hold it in memory,
                     and expose a human-readable "context window"
                     that describes the project state.
    Class          : ContextStore
    Analogy        : The "working memory" of the system — everything
                     the downstream layers know about a project.

  Layer 2 -- Processor  (mcp/processor.py)
    Responsibility : Analyse the raw data in the ContextStore and
                     compute all derived metrics (completion, risk,
                     timeline, resource allocation, priorities).
    Class          : Processor
    Analogy        : The "reasoning engine" — transforms raw facts
                     into actionable intelligence.

  Layer 3 -- Responder  (mcp/responder.py)
    Responsibility : Accept a natural-language question, match it
                     to the right answer template, and produce a
                     structured plain-text answer using only the
                     metrics already computed by the Processor.
    Class          : Responder
    Analogy        : The "response generator" — never invents data,
                     only formats what the Processor computed.

Full pipeline:

    raw_data  →  ContextStore.load()
              →  Processor.process(context)
              →  Responder.answer(question, context)
              →  plain-text answer

Design principles:
  * Each layer reads only from the layer before it.
  * No layer makes network calls.
  * No layer generates or guesses data.
  * The ContextStore is the single source of truth at runtime.
"""

__version__ = "1.0.0"
__all__ = ["context", "processor", "responder"]
