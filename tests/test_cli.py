import pytest

from revenant import __version__
from revenant.cli import main


def test_main_without_args_prints_help(capsys):
    assert main([]) == 0
    assert "usage: revenant" in capsys.readouterr().out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
