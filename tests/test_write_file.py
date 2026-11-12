import pytest

from revenant.sink import EffectSink
from revenant.tools import ToolError, WriteFile


def test_writes_inside_sandbox(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    tool = WriteFile(tmp_path / "box")
    tool.perform({"relpath": "a/b.txt", "content": "hi"}, sink)
    assert (tmp_path / "box" / "a" / "b.txt").read_text() == "hi"
    assert sink.effects() == [{"tool": "write_file", "relpath": "a/b.txt", "content": "hi"}]


@pytest.mark.parametrize(
    "path", ["/etc/passwd", "../x", "a/../../x", "a/..", "C:\\x", "\\abs"]
)
def test_escapes_rejected(tmp_path, path):
    sink = EffectSink(tmp_path / "s.jsonl")
    tool = WriteFile(tmp_path / "box")
    with pytest.raises(ToolError):
        tool.perform({"relpath": path, "content": "x"}, sink)
    assert sink.effects() == []


def test_symlink_escape_rejected(tmp_path):
    box = tmp_path / "box"
    box.mkdir()
    (box / "link").symlink_to(tmp_path)
    with pytest.raises(ToolError, match="escapes"):
        WriteFile(box).perform(
            {"relpath": "link/x.txt", "content": "x"}, EffectSink(tmp_path / "s.jsonl")
        )
    assert not (tmp_path / "x.txt").exists()


@pytest.mark.parametrize(
    "bad", [{"content": "x"}, {"relpath": "a"}, {"relpath": "", "content": "x"},
            {"relpath": "a", "content": 3}]
)
def test_bad_args(tmp_path, bad):
    with pytest.raises(ToolError):
        WriteFile(tmp_path).idempotency_key(bad)


def test_key_depends_on_path_and_content(tmp_path):
    t = WriteFile(tmp_path)
    k = t.idempotency_key({"relpath": "a", "content": "1"})
    assert k.startswith("write_file:")
    assert k != t.idempotency_key({"relpath": "a", "content": "2"})
    assert k != t.idempotency_key({"relpath": "b", "content": "1"})
