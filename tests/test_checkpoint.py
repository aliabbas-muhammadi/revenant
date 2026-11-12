import json

import pytest

from revenant.checkpoint import SCHEMA_VERSION, CheckpointError, load_checkpoint, write_checkpoint


def test_missing_checkpoint_is_none(tmp_path):
    assert load_checkpoint(tmp_path / "ckpt.json") is None


def test_roundtrip_and_contents(tmp_path):
    path = tmp_path / "ckpt.json"
    write_checkpoint(path, {"completed": 5, "trace": ["a"]})
    on_disk = json.loads(path.read_text())
    assert on_disk == {"schema_version": SCHEMA_VERSION, "completed": 5, "trace": ["a"]}
    assert load_checkpoint(path) == on_disk


def test_no_temp_file_left_behind(tmp_path):
    path = tmp_path / "ckpt.json"
    write_checkpoint(path, {"completed": 1})
    write_checkpoint(path, {"completed": 2})
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ckpt.json"]
    assert load_checkpoint(path)["completed"] == 2


def test_unknown_schema_version_rejected(tmp_path):
    path = tmp_path / "ckpt.json"
    path.write_text(json.dumps({"schema_version": 99, "completed": 1}))
    with pytest.raises(CheckpointError, match="99"):
        load_checkpoint(path)


def test_missing_schema_version_rejected(tmp_path):
    path = tmp_path / "ckpt.json"
    path.write_text(json.dumps({"completed": 1}))
    with pytest.raises(CheckpointError):
        load_checkpoint(path)


def test_garbage_rejected(tmp_path):
    path = tmp_path / "ckpt.json"
    path.write_text("{not json")
    with pytest.raises(CheckpointError):
        load_checkpoint(path)
