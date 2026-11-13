"""Human-readable renderings of a :class:`~revenant.conformance.ConformanceResult`."""

from __future__ import annotations

from revenant.conformance import ConformanceResult


def summary_line(result: ConformanceResult, planned: int | None = None) -> str:
    """The headline line from DESIGN.md.

    ``planned`` is the number of boundaries the sweep set out to kill at; it
    defaults to the number actually scored. Duplicated and lost/phantom counts
    appear only when non-zero, so a clean pass keeps the canonical shape.
    """
    total = result.total
    parts = [
        f"killed at {total}/{planned if planned is not None else total} boundaries",
        f"resumes: {result.identical_resumes}/{total} identical",
        f"effects: {result.effects_once} once each",
    ]
    if result.duplicated:
        parts.append(f"duplicated: {result.duplicated}")
    if result.lost_or_phantom:
        parts.append(f"lost/phantom steps: {result.lost_or_phantom}")
    parts.append(f"unconfirmed: {result.unconfirmed}")
    parts.append(f"verdict: {result.verdict.value}")
    return " · ".join(parts)


def markdown_report(result: ConformanceResult, planned: int | None = None) -> str:
    """A heading, the summary line and one table row per boundary."""
    lines = [
        f"# {result.adapter} · {result.workload}",
        "",
        summary_line(result, planned),
        "",
        "| boundary | mode | resume | effects once | duplicated | missing | unconfirmed "
        "| lost | phantom | result |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for b in result.boundaries:
        resume = "identical" if b.determinism.passed else (
            f"diverged at step {b.determinism.first_divergent_step}"
            if b.determinism.first_divergent_step is not None
            else "final state differs"
        )
        e = b.effects
        lines.append(
            f"| {b.boundary} | {b.mode} | {resume} | {e.once} | {len(e.duplicated)} "
            f"| {len(e.missing)} | {len(e.unconfirmed)} | {len(b.steps.lost)} "
            f"| {len(b.steps.phantom)} | {'pass' if b.passed else 'FAIL'} |"
        )
    return "\n".join(lines) + "\n"
