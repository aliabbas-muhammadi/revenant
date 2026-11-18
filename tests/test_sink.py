from revenant.sink import EffectSink


def test_missing_file_is_empty(tmp_path):
    assert EffectSink(tmp_path / "sink.jsonl").effects() == []


def test_appends_in_order_and_survives_reopen(tmp_path):
    path = tmp_path / "sub" / "sink.jsonl"
    sink = EffectSink(path)
    sink.append({"tool": "send_email", "to": "a@example.com"})
    sink.append({"tool": "charge_card", "amount_cents": 500})
    again = EffectSink(path)
    again.append({"tool": "write_file", "path": "é.txt"})
    assert [e["tool"] for e in EffectSink(path).effects()] == [
        "send_email",
        "charge_card",
        "write_file",
    ]


def test_duplicates_are_kept(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    sink.append({"k": 1})
    sink.append({"k": 1})
    assert sink.effects() == [{"k": 1}, {"k": 1}]


def test_one_record_per_line(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    sink.append({"text": "a\nb"})
    assert len(sink.path.read_text().splitlines()) == 1


def test_len_counts_whole_records(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    assert len(sink) == 0
    sink.append({"k": 1})
    sink.append({"k": 1})
    assert len(sink) == 2


def test_len_ignores_torn_final_line(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    sink.append({"k": 1})
    with open(sink.path, "ab") as fh:
        fh.write(b'{"k": ')
    assert len(sink) == 1


def test_by_tool_counts_sorted(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    for tool in ["write_file", "send_email", "send_email"]:
        sink.append({"tool": tool})
    sink.append({"other": 1})
    assert sink.by_tool() == {"send_email": 2, "write_file": 1}
    assert list(sink.by_tool()) == ["send_email", "write_file"]


def test_iter_yields_records_in_order(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    sink.append({"n": 1})
    sink.append({"n": 2})
    assert [r["n"] for r in sink] == [1, 2]
    assert list(EffectSink(tmp_path / "missing.jsonl")) == []


def test_last_returns_most_recent_or_none(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    assert sink.last() is None
    sink.append({"n": 1})
    sink.append({"n": 2})
    assert sink.last() == {"n": 2}


def test_first_returns_earliest_or_none(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    assert sink.first() is None
    sink.append({"tool": "a", "n": 1})
    sink.append({"tool": "b", "n": 2})
    assert sink.first() == {"tool": "a", "n": 1}
    assert sink.last() == {"tool": "b", "n": 2}



def test_count_by_tool(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    assert sink.count("a") == 0
    sink.append({"tool": "a"})
    sink.append({"tool": "a"})
    sink.append({"tool": "b"})
    sink.append({"no_tool": 1})
    assert sink.count("a") == 2
    assert sink.count("b") == 1
    assert sink.count("c") == 0


def test_tools_lists_distinct_sorted(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    assert sink.tools() == []
    sink.append({"tool": "write_file"})
    sink.append({"tool": "charge_card"})
    sink.append({"tool": "write_file"})
    sink.append({"other": 1})
    assert sink.tools() == ["charge_card", "write_file"]


def test_filter_keeps_append_order(tmp_path):
    sink = EffectSink(tmp_path / "s.jsonl")
    assert sink.filter("a") == []
    sink.append({"tool": "a", "n": 1})
    sink.append({"tool": "b", "n": 2})
    sink.append({"tool": "a", "n": 3})
    assert sink.filter("a") == [{"tool": "a", "n": 1}, {"tool": "a", "n": 3}]
    assert sink.filter("c") == []


def test_since_returns_tail_and_rejects_negative(tmp_path):
    import pytest

    sink = EffectSink(tmp_path / "s.jsonl")
    for n in range(4):
        sink.append({"n": n})
    assert sink.since(0) == sink.effects()
    assert sink.since(2) == [{"n": 2}, {"n": 3}]
    assert sink.since(9) == []
    with pytest.raises(ValueError):
        sink.since(-1)
