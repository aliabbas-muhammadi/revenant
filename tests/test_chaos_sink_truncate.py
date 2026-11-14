import pytest

from revenant.chaos import truncate_file
from revenant.sink import EffectSink, SinkCorrupt


def _sink(tmp_path):
    sink = EffectSink(tmp_path / "effects.jsonl")
    sink.append({"tool": "send_email", "to": "a@example.com"})
    sink.append({"tool": "charge_card", "customer": "c1", "amount_cents": 100})
    return sink


def test_clean_sink_has_no_partial(tmp_path):
    result = _sink(tmp_path).read()
    assert len(result.effects) == 2 and result.partial is None


def test_truncated_final_line_is_reported(tmp_path):
    sink = _sink(tmp_path)
    size = sink.path.stat().st_size
    truncate_file(sink.path, size - 10)
    result = sink.read()
    assert len(result.effects) == 1
    assert result.partial is not None and result.partial.startswith('{"amount_cents"')


def test_effects_raises_on_partial_record(tmp_path):
    sink = _sink(tmp_path)
    truncate_file(sink.path, sink.path.stat().st_size - 10)
    with pytest.raises(SinkCorrupt, match="partial record"):
        sink.effects()


def test_garbage_in_the_middle_names_its_line(tmp_path):
    sink = _sink(tmp_path)
    sink.path.write_text('{"a": 1}\nnot json\n{"b": 2}\n')
    with pytest.raises(SinkCorrupt, match="line 2"):
        sink.read()


def test_cut_exactly_at_a_record_boundary_is_clean(tmp_path):
    sink = _sink(tmp_path)
    first = sink.path.read_bytes().index(b"\n") + 1
    truncate_file(sink.path, first)
    result = sink.read()
    assert len(result.effects) == 1 and result.partial is None


def test_missing_sink_is_empty(tmp_path):
    assert EffectSink(tmp_path / "none.jsonl").read().effects == []
