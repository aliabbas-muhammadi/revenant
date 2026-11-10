from revenant.canon import canonical_json


def test_key_order_independence():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_compact_separators_and_sorted_keys():
    assert canonical_json({"b": 1, "a": [1, 2]}) == b'{"a":[1,2],"b":1}'


def test_nested_dicts_and_lists():
    left = {"x": [{"b": 1, "a": 2}, {"d": 3, "c": 4}], "y": {"q": 1, "p": 2}}
    right = {"y": {"p": 2, "q": 1}, "x": [{"a": 2, "b": 1}, {"c": 4, "d": 3}]}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_json(left) == (
        b'{"x":[{"a":2,"b":1},{"c":4,"d":3}],"y":{"p":2,"q":1}}'
    )


def test_list_order_is_significant():
    assert canonical_json([1, 2]) != canonical_json([2, 1])


def test_non_ascii_is_emitted_as_utf8():
    assert canonical_json({"k": "é"}) == '{"k":"é"}'.encode()


def test_nfc_normalises_values():
    composed, decomposed = "é", "é"
    assert composed != decomposed
    assert canonical_json({"k": composed}) == canonical_json({"k": decomposed})


def test_nfc_normalises_keys_and_nested_strings():
    composed, decomposed = "café", "café"
    assert canonical_json({decomposed: [decomposed]}) == canonical_json({composed: [composed]})
