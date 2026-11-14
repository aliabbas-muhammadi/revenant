"""LangGraph adapter, built up in stages: graph builder and SQLite checkpointer.

Each workload step becomes one node. The graph state has the same shape as the
reference runtime's state, so a clean run hashes identically to the reference.
Requires the ``langgraph`` extra.

Boundaries: LangGraph persists state once per superstep. In the linear graph every
node is its own superstep, so ``boundaries()`` is the superstep count, equal to the
number of steps. Boundary ``k`` means the process dies with ``k`` supersteps
checkpointed and nothing of superstep ``k + 1`` started. Mid-step kill ``k`` dies
inside node ``k`` after its tool effect but before the superstep is saved, so
LangGraph re-runs that node on resume.
"""

from __future__ import annotations

import os
import signal
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


def die() -> None:
    """SIGKILL this process: no cleanup handlers run, which is the crash under test."""
    os.kill(os.getpid(), signal.SIGKILL)


def build_graph(
    workload: Workload,
    workdir: str | Path,
    kill_at: int | None = None,
    kill_mid: bool = False,
) -> StateGraph:
    """One node per step, chained ``START -> step_0 -> ... -> END`` (uncompiled).

    With ``kill_at=k`` the process dies at boundary ``k`` (``1..N-1`` here; the final
    boundary is the caller's, once the graph returns). ``kill_mid`` instead dies in
    node ``k - 1`` after its tool effect and before its superstep is saved.
    """
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    model = ScriptedModel(workload.script)
    sink = EffectSink(root / "effects.jsonl")
    attempts = AttemptCounter()

    def make_node(index: int):
        spec = workload.steps[index]

        def node(state: GraphState) -> GraphState:
            if kill_at is not None and not kill_mid and index == kill_at:
                die()
            clock = InjectedClock(state["clock"])
            clock.tick()
            results = dict(state["results"])
            if spec.tool is not None:
                tool = get_tool(spec.tool, root / "sandbox")
                with Ledger(root / "ledger.db") as ledger:
                    results[spec.name] = invoke(tool, spec.args, sink, ledger, attempts).key
            if kill_at is not None and kill_mid and index + 1 == kill_at:
                die()
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


def compile_graph(
    workload: Workload,
    workdir: str | Path,
    checkpointer: SqliteSaver,
    interrupt_after: list[str] | None = None,
    kill_at: int | None = None,
    kill_mid: bool = False,
) -> Any:
    """Compile the workload graph with ``checkpointer`` attached.

    ``interrupt_after`` names nodes to pause after; it exists so tests can leave a
    partial run behind without killing a process.
    """
    return build_graph(workload, workdir, kill_at, kill_mid).compile(
        checkpointer=checkpointer, interrupt_after=interrupt_after
    )


def run_or_resume(graph: Any) -> dict[str, Any]:
    """Start the workload, or continue it if the thread already has a checkpoint.

    Resuming invokes the same ``thread_id`` with ``None`` as input, which tells
    LangGraph to continue from the last saved superstep instead of restarting.
    """
    config = thread_config()
    if graph.get_state(config).created_at is None:
        return graph.invoke(initial_state(), config)
    return graph.invoke(None, config)
