import os
import sys

import pytest

from revenant.runner import ChildStatus, classify_exit, spawn_child

pytestmark = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _py(code):
    return [sys.executable, "-c", code]


def test_completed_child_captures_output():
    out = spawn_child(_py("print('hi')"))
    assert out.status is ChildStatus.COMPLETED
    assert out.stdout.strip() == "hi"


def test_killed_child_is_classified():
    code = "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"
    out = spawn_child(_py(code))
    assert out.status is ChildStatus.KILLED
    assert out.returncode == -9


def test_error_child_keeps_stderr():
    out = spawn_child(_py("import sys; sys.stderr.write('boom'); sys.exit(3)"))
    assert out.status is ChildStatus.ERROR
    assert out.returncode == 3 and out.stderr == "boom"


def test_env_is_passed_to_child():
    out = spawn_child(_py("import os; print(os.environ['X_TEST'])"), env={"X_TEST": "v"})
    assert out.stdout.strip() == "v"


def test_inherited_kill_env_is_scrubbed(monkeypatch):
    monkeypatch.setenv("REVENANT_KILL_AT", "4")
    out = spawn_child(_py("import os; print(os.environ.get('REVENANT_KILL_AT'))"))
    assert out.stdout.strip() == "None"


def test_classify_exit_codes():
    assert classify_exit(0) is ChildStatus.COMPLETED
    assert classify_exit(-9) is ChildStatus.KILLED
    assert classify_exit(1) is ChildStatus.ERROR
    assert classify_exit(-15) is ChildStatus.ERROR


def test_timeout_is_a_hang_not_a_crash():
    import sys

    from revenant.runner import ChildStatus, spawn_child

    out = spawn_child(
        [sys.executable, "-c", "import time; print('hi', flush=True); time.sleep(30)"],
        timeout=1.0,
    )
    assert out.status is ChildStatus.HANG
    assert out.status is not ChildStatus.KILLED and out.status is not ChildStatus.ERROR
