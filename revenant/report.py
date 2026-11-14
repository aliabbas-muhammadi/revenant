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
    if result.chaos != "none":
        parts.append(f"chaos: {result.chaos}")
        if result.damaged:
            parts.append(f"damage refused: {result.refused}/{result.damaged}")
    parts.append(f"verdict: {result.verdict.value}")
    return " · ".join(parts)


def markdown_report(result: ConformanceResult, planned: int | None = None) -> str:
    """A heading, the summary line and one table row per boundary."""
    return markdown_from_dict(report_dict(result, planned, versions={}))


REPORT_SCHEMA_VERSION = 1


def _installed(dist: str) -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(dist)
    except PackageNotFoundError:
        return "unknown"


def versions_header(adapter: str | None = None) -> dict[str, str]:
    """Library and platform versions; durability behaviour changes across releases.

    Adapters built on a third-party runtime add that runtime's version, since its
    checkpointing behaviour is what the report is really about.
    """
    import platform
    import sys

    from revenant import __version__

    header = {
        "python": sys.version.split()[0],
        "revenant": __version__,
        "platform": platform.platform(),
    }
    if adapter == "langgraph_sqlite":
        header["langgraph"] = _installed("langgraph")
        header["langgraph-checkpoint-sqlite"] = _installed("langgraph-checkpoint-sqlite")
    return header


def report_dict(
    result: ConformanceResult,
    planned: int | None = None,
    versions: dict[str, str] | None = None,
) -> dict[str, object]:
    """The full report as plain data, ready for ``json.dumps``."""
    data: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "versions": versions if versions is not None else versions_header(result.adapter),
        "adapter": result.adapter,
        "workload": result.workload,
        "verdict": result.verdict.value,
        "summary": summary_line(result, planned),
        "boundaries": [
            {
                "boundary": b.boundary,
                "mode": b.mode,
                "passed": b.passed,
                "determinism": {
                    "passed": b.determinism.passed,
                    "first_divergent_step": b.determinism.first_divergent_step,
                    "final_state_matches": b.determinism.final_state_matches,
                    "detail": b.determinism.detail,
                },
                "effects": {
                    "once": b.effects.once,
                    "duplicated": list(b.effects.duplicated),
                    "missing": list(b.effects.missing),
                    "unexpected": list(b.effects.unexpected),
                    "unconfirmed": list(b.effects.unconfirmed),
                },
                "steps": {"lost": list(b.steps.lost), "phantom": list(b.steps.phantom)},
            }
            for b in result.boundaries
        ],
    }
    if result.chaos != "none":
        # Additive keys: reports of plain runs keep their original shape.
        data["chaos"] = result.chaos
        for entry, b in zip(data["boundaries"], result.boundaries, strict=True):  # type: ignore[arg-type]
            if b.detected is not None:
                entry["detected"] = b.detected  # type: ignore[index]
    return data


def json_report(
    result: ConformanceResult,
    planned: int | None = None,
    versions: dict[str, str] | None = None,
) -> str:
    """Stable JSON text: sorted keys, two-space indent, trailing newline."""
    import json

    return json.dumps(report_dict(result, planned, versions), indent=2, sort_keys=True) + "\n"


def markdown_from_dict(data: dict[str, object]) -> str:
    """Render the markdown report from a parsed JSON report (see :func:`report_dict`)."""
    chaos = data.get("chaos")
    lines = [
        f"# {data['adapter']} · {data['workload']}",
        "",
        str(data["summary"]),
        "",
        "| boundary | mode | resume | effects once | duplicated | missing | unconfirmed "
        "| lost | phantom |" + (" chaos | damage |" if chaos else "") + " result |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|" + ("---|---|" if chaos else "") + "---|",
    ]
    for b in data["boundaries"]:  # type: ignore[attr-defined]
        det, eff, steps = b["determinism"], b["effects"], b["steps"]
        if det["passed"]:
            resume = "identical"
        elif det["first_divergent_step"] is not None:
            resume = f"diverged at step {det['first_divergent_step']}"
        else:
            resume = "final state differs"
        extra = ""
        if chaos:
            detected = b.get("detected")
            damage = "-" if detected is None else ("refused" if detected else "NOT detected")
            extra = f"| {chaos} | {damage} "
            if detected:
                resume = "refused (damage detected)"
        lines.append(
            f"| {b['boundary']} | {b['mode']} | {resume} | {eff['once']} "
            f"| {len(eff['duplicated'])} | {len(eff['missing'])} | {len(eff['unconfirmed'])} "
            f"| {len(steps['lost'])} | {len(steps['phantom'])} {extra}"
            f"| {'pass' if b['passed'] else 'FAIL'} |"
        )
    return "\n".join(lines) + "\n"
