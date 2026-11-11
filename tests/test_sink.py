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
