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


REPORT_SCHEMA_VERSION = 1


def versions_header() -> dict[str, str]:
    """Library and platform versions; durability behaviour changes across releases."""
    import platform
    import sys

    from revenant import __version__

    return {
        "python": sys.version.split()[0],
        "revenant": __version__,
        "platform": platform.platform(),
    }


def report_dict(
    result: ConformanceResult,
    planned: int | None = None,
    versions: dict[str, str] | None = None,
) -> dict[str, object]:
    """The full report as plain data, ready for ``json.dumps``."""
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "versions": versions if versions is not None else versions_header(),
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


def json_report(
    result: ConformanceResult,
    planned: int | None = None,
    versions: dict[str, str] | None = None,
) -> str:
    """Stable JSON text: sorted keys, two-space indent, trailing newline."""
    import json

    return json.dumps(report_dict(result, planned, versions), indent=2, sort_keys=True) + "\n"
