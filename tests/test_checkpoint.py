import json

import pytest

from revenant.checkpoint import (
    SCHEMA_VERSION,
    CheckpointCorrupt,
    CheckpointError,
    _digest,
    load_checkpoint,
    write_checkpoint,
)


def test_missing_checkpoint_is_none(tmp_path):
    assert load_checkpoint(tmp_path / "ckpt.json") is None


def test_roundtrip_and_contents(tmp_path):
    path = tmp_path / "ckpt.json"
    write_checkpoint(path, {"completed": 5, "trace": ["a"]})
    on_disk = json.loads(path.read_text())
    expected = {"schema_version": SCHEMA_VERSION, "completed": 5, "trace": ["a"]}
    assert on_disk["body"] == expected
    assert len(on_disk["digest"]) == 64
    assert load_checkpoint(path) == expected


def test_no_temp_file_left_behind(tmp_path):
    path = tmp_path / "ckpt.json"
    write_checkpoint(path, {"completed": 1})
    write_checkpoint(path, {"completed": 2})
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ckpt.json"]
    assert load_checkpoint(path)["completed"] == 2


def test_unknown_schema_version_rejected(tmp_path):
    path = tmp_path / "ckpt.json"
    write_checkpoint(path, {"completed": 1})
    doc = json.loads(path.read_text())
    doc["body"]["schema_version"] = 99
    doc["digest"] = _digest(doc["body"])
    path.write_text(json.dumps(doc))
    with pytest.raises(CheckpointError, match="99"):
        load_checkpoint(path)


def test_missing_schema_version_rejected(tmp_path):
    path = tmp_path / "ckpt.json"
    body = {"completed": 1}
    path.write_text(json.dumps({"body": body, "digest": _digest(body)}))
    with pytest.raises(CheckpointError):
        load_checkpoint(path)


def test_garbage_rejected(tmp_path):
    path = tmp_path / "ckpt.json"
    path.write_text("{not json")
    with pytest.raises(CheckpointError):
        load_checkpoint(path)


def test_truncated_file_is_corrupt(tmp_path):
    path = tmp_path / "ckpt.json"
    write_checkpoint(path, {"completed": 3, "trace": ["a", "b", "c"]})
    raw = path.read_bytes()
    path.write_bytes(raw[: len(raw) // 2])
    with pytest.raises(CheckpointCorrupt):
        load_checkpoint(path)


def test_digest_mismatch_is_corrupt(tmp_path):
    path = tmp_path / "ckpt.json"
    write_checkpoint(path, {"completed": 3})
    doc = json.loads(path.read_text())
    doc["body"]["completed"] = 4
    path.write_text(json.dumps(doc))
    with pytest.raises(CheckpointCorrupt, match="digest"):
        load_checkpoint(path)


def test_corrupt_is_a_checkpoint_error():
    assert issubclass(CheckpointCorrupt, CheckpointError)
