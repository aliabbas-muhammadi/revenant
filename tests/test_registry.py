import pytest

from revenant.tools import ChargeCard, SendEmail, ToolError, WriteFile, get_tool


def test_known_tools(tmp_path):
    assert isinstance(get_tool("send_email"), SendEmail)
    assert isinstance(get_tool("charge_card"), ChargeCard)
    assert isinstance(get_tool("write_file", tmp_path), WriteFile)


def test_unknown_tool_lists_known():
    with pytest.raises(ToolError) as exc:
        get_tool("nope")
    msg = str(exc.value)
    assert "'nope'" in msg
    for name in ("send_email", "charge_card", "write_file"):
        assert name in msg


def test_write_file_needs_sandbox():
    with pytest.raises(ToolError, match="sandbox"):
        get_tool("write_file")
