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

import argparse
import json
import os
import signal
import sqlite3
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from revenant.adapter import Adapter
from revenant.adapters.reference import KILL_ENV, KILL_MODE_ENV, KILL_MODES
from revenant.canon import state_hash
from revenant.clock import InjectedClock
from revenant.ledger import Ledger
from revenant.model import ScriptedModel
from revenant.result import RunResult
from revenant.sink import EffectSink
from revenant.tools import AttemptCounter, get_tool, invoke
from revenant.workloads import Workload, get_workload


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
    naive_tools: bool = False,
) -> StateGraph:
    """One node per step, ``START -> step_0 -> ... -> END`` (uncompiled).

    Every node leaves through a conditional edge, so a ``stop`` response from the
    scripted model ends the run early (the ``branching`` tool loop).

    With ``kill_at=k`` the process dies at boundary ``k`` (``1..N-1`` here; the final
    boundary is the caller's, once the graph returns). ``kill_mid`` instead dies in
    node ``k - 1`` after its tool effect and before its superstep is saved.
    ``naive_tools`` bypasses the effects ledger (the default is ledgered tools).
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
                    results[spec.name] = invoke(
                        tool, spec.args, sink, ledger, attempts, naive=naive_tools
                    ).key
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
    for i, name in enumerate(names):
        following = names[i + 1] if i + 1 < len(names) else END
        graph.add_conditional_edges(name, make_router(following), [following, END])
    return graph


def make_router(following: str):
    """Conditional edge: end the run once the model's last response says ``stop``.

    Otherwise continue to ``following``. Scripts without an ``action`` key (the
    linear workload) never stop early, so they run every node.
    """

    def route(state: GraphState) -> str:
        last = state["thoughts"][-1] if state["thoughts"] else None
        if isinstance(last, dict) and last.get("action") == "stop":
            return END
        return following

    return route


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
    naive_tools: bool = False,
) -> Any:
    """Compile the workload graph with ``checkpointer`` attached.

    ``interrupt_after`` names nodes to pause after; it exists so tests can leave a
    partial run behind without killing a process.
    """
    return build_graph(workload, workdir, kill_at, kill_mid, naive_tools).compile(
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


def hash_trace(graph: Any, workload: Workload) -> tuple[str, ...]:
    """Per-step state hashes read back from the saved supersteps, in step order.

    Volatile fields are excluded exactly as for the reference runtime, so a clean
    LangGraph run produces the same trace as the reference.
    """
    by_step: dict[int, str] = {}
    for snap in graph.get_state_history(thread_config()):
        step = snap.values.get("step", 0)
        if step >= 1:
            by_step[step] = state_hash(dict(snap.values), workload.volatile_fields)
    return tuple(by_step[k] for k in sorted(by_step))


class LangGraphAdapter(Adapter):
    """LangGraph with ``SqliteSaver``, resumed by ``thread_id``."""

    name = "langgraph_sqlite"

    def __init__(self, naive_tools: bool = False) -> None:
        #: Bypass the ledger; the default routes every tool call through it.
        self.naive_tools = naive_tools
        self._workload: Workload | None = None
        self._workdir: Path | None = None

    def build(self, workload: Workload, workdir: str | Path) -> None:
        self._workload = workload
        self._workdir = Path(workdir)
        self._workdir.mkdir(parents=True, exist_ok=True)

    def _built(self) -> tuple[Workload, Path]:
        if self._workload is None or self._workdir is None:
            raise RuntimeError("call build() before run()")
        return self._workload, self._workdir

    def run(self, kill_at: int | None = None) -> RunResult:
        """Run or resume; ``kill_at`` (or ``REVENANT_KILL_AT``) kills at that boundary."""
        workload, root = self._built()
        if kill_at is None and os.environ.get(KILL_ENV):
            kill_at = int(os.environ[KILL_ENV])
        mode = os.environ.get(KILL_MODE_ENV, "boundary")
        if mode not in KILL_MODES:
            raise ValueError(f"{KILL_MODE_ENV} must be one of {KILL_MODES}, got {mode!r}")
        saver = open_checkpointer(root)
        try:
            graph = compile_graph(
                workload, root, saver,
                kill_at=kill_at, kill_mid=mode == "mid", naive_tools=self.naive_tools,
            )  # fmt: skip
            run_or_resume(graph)
            if kill_at == len(workload.steps) and mode == "boundary":
                die()  # the last boundary: everything saved, nothing left to run
            trace = hash_trace(graph, workload)
        finally:
            saver.conn.close()
        return RunResult(True, len(trace), trace)

    def state_trace(self) -> tuple[str, ...]:
        workload, root = self._built()
        if not (root / CHECKPOINT_DB).exists():
            return ()
        saver = open_checkpointer(root)
        try:
            return hash_trace(compile_graph(workload, root, saver), workload)
        finally:
            saver.conn.close()

    def boundaries(self) -> int:
        """Superstep count: one per step for the linear graph."""
        workload, _ = self._built()
        return len(workload.steps)


def main(argv: list[str] | None = None) -> int:
    """Child entry point, mirroring the reference adapter's."""
    parser = argparse.ArgumentParser(prog="python -m revenant.adapters.langgraph_sqlite")
    parser.add_argument("--workload", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--naive-tools", action="store_true", help="bypass the effects ledger")
    args = parser.parse_args(argv)
    adapter = LangGraphAdapter(naive_tools=args.naive_tools)
    adapter.build(get_workload(args.workload), args.workdir)
    result = adapter.run()
    print(json.dumps({"completed": result.completed, "steps_run": result.steps_run}))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
