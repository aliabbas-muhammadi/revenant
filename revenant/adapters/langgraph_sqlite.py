"""LangGraph adapter, built up in stages: graph builder and SQLite checkpointer.

Each workload step becomes one node. The graph state has the same shape as the
reference runtime's state, so a clean run hashes identically to the reference.
Requires the ``langgraph`` extra.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from revenant.clock import InjectedClock
from revenant.ledger import Ledger
from revenant.model import ScriptedModel
from revenant.sink import EffectSink
from revenant.tools import AttemptCounter, get_tool, invoke
from revenant.workloads import Workload


class GraphState(TypedDict):
    step: int
    thoughts: list[Any]
    results: dict[str, str]
    clock: float


def initial_state() -> GraphState:
    return {"step": 0, "thoughts": [], "results": {}, "clock": 0.0}


def build_graph(workload: Workload, workdir: str | Path) -> StateGraph:
    """One node per step, chained ``START -> step_0 -> ... -> END`` (uncompiled)."""
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    model = ScriptedModel(workload.script)
    sink = EffectSink(root / "effects.jsonl")
    attempts = AttemptCounter()

    def make_node(index: int):
        spec = workload.steps[index]

        def node(state: GraphState) -> GraphState:
            clock = InjectedClock(state["clock"])
            clock.tick()
            results = dict(state["results"])
            if spec.tool is not None:
                tool = get_tool(spec.tool, root / "sandbox")
                with Ledger(root / "ledger.db") as ledger:
                    results[spec.name] = invoke(tool, spec.args, sink, ledger, attempts).key
            return {
                "step": index + 1,
                "thoughts": [*state["thoughts"], model.respond(index)],
                "results": results,
                "clock": clock.now(),
            }

        return node

    graph = StateGraph(GraphState)
    names = [f"step_{i}" for i in range(len(workload.steps))]
    for i, name in enumerate(names):
        graph.add_node(name, make_node(i))
    graph.add_edge(START, names[0])
    for a, b in zip(names, names[1:], strict=False):
        graph.add_edge(a, b)
    graph.add_edge(names[-1], END)
    return graph


CHECKPOINT_DB = "langgraph.sqlite"
#: One thread per workdir; resuming means invoking the same thread again.
THREAD_ID = "revenant"


def thread_config() -> dict[str, Any]:
    """The ``config`` that pins every invocation to the fixed thread."""
    return {"configurable": {"thread_id": THREAD_ID}}


def open_checkpointer(workdir: str | Path) -> SqliteSaver:
    """A ``SqliteSaver`` over ``<workdir>/langgraph.sqlite``; the caller closes it."""
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / CHECKPOINT_DB, check_same_thread=False)
    return SqliteSaver(conn)


def compile_graph(workload: Workload, workdir: str | Path, checkpointer: SqliteSaver) -> Any:
    """Compile the workload graph with ``checkpointer`` attached."""
    return build_graph(workload, workdir).compile(checkpointer=checkpointer)
