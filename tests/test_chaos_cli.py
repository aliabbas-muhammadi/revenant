import pytest

from revenant.chaos import (
    CHAOS_ENV,
    CHAOS_MODES,
    damages_checkpoint,
    injections,
    injections_from_env,
)
from revenant.cli import main


def test_modes_map_to_injections():
    assert injections("none") == frozenset()
    assert injections("dup") == {"dup"}
    assert injections("timeout") == {"timeout"}
    assert injections("all") == {"dup", "timeout"}
    assert [m for m in CHAOS_MODES if damages_checkpoint(m)] == ["corrupt", "all"]


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="unknown chaos mode"):
        injections("bogus")


def test_injections_read_from_env():
    assert injections_from_env({CHAOS_ENV: "dup,timeout"}) == {"dup", "timeout"}
    assert injections_from_env({}) == frozenset()


@pytest.mark.parametrize("mode", ["dup", "timeout"])
def test_injection_modes_still_pass(mode, capsys):
    code = main(["run", "--adapter", "reference", "--workload", "linear",
                 "--kill-at", "4", "--chaos", mode])  # fmt: skip
    assert code == 0
    assert "verdict: PASS" in capsys.readouterr().out


def test_corrupt_mode_passes_when_damage_is_refused(capsys):
    code = main(["run", "--adapter", "reference", "--workload", "linear",
                 "--kill-at", "4", "--chaos", "corrupt"])  # fmt: skip
    assert code == 0
    assert "verdict: PASS" in capsys.readouterr().out


def test_corrupt_mode_fails_a_runtime_that_ignores_damage(capsys):
    # the nocheckpoint mutant never reads its checkpoint, so it cannot refuse a damaged one
    code = main(["run", "--adapter", "mutant_nocheckpoint", "--workload", "linear",
                 "--kill-at", "4", "--chaos", "corrupt"])  # fmt: skip
    assert code == 1


def test_all_mode_runs(capsys):
    code = main(["run", "--adapter", "reference", "--workload", "linear",
                 "--kill-at", "3", "--chaos", "all"])  # fmt: skip
    assert code == 0


def test_chaos_rejected_for_langgraph(capsys):
    pytest.importorskip("langgraph.checkpoint.sqlite")
    with pytest.raises(SystemExit) as exc:
        main(["run", "--adapter", "langgraph_sqlite", "--workload", "linear",
              "--chaos", "dup"])  # fmt: skip
    assert exc.value.code == 2


def test_chaos_env_is_restored_after_a_sweep(monkeypatch):
    monkeypatch.delenv(CHAOS_ENV, raising=False)
    import os

    main(["run", "--adapter", "reference", "--workload", "linear",
          "--kill-at", "2", "--chaos", "dup"])  # fmt: skip
    assert CHAOS_ENV not in os.environ
