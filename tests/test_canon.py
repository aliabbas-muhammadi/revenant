import pytest

from revenant.canon import CanonError, canonical_json


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


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_rejected(value):
    with pytest.raises(CanonError):
        canonical_json(value)
    with pytest.raises(CanonError):
        canonical_json({"a": [value]})


def test_tuples_encode_as_lists():
    assert canonical_json((1, (2, 3))) == canonical_json([1, [2, 3]])


@pytest.mark.parametrize(
    ("value", "path", "type_name"),
    [
        ({1, 2}, "$", "set"),
        (b"x", "$", "bytes"),
        (object(), "$", "object"),
        ({"a": [1, 2, {3}]}, "$.a[2]", "set"),
        ({"a": {"b": b"x"}}, "$.a.b", "bytes"),
    ],
)
def test_unsupported_types_name_type_and_path(value, path, type_name):
    with pytest.raises(CanonError) as exc:
        canonical_json(value)
    assert type_name in str(exc.value)
    assert path in str(exc.value)


def test_non_finite_error_names_path():
    with pytest.raises(CanonError, match=r"\$\.a\[1\]"):
        canonical_json({"a": [1, float("nan")]})


@pytest.mark.parametrize("key", [1, None, 1.5, (1, 2)])
def test_non_string_keys_rejected(key):
    with pytest.raises(CanonError, match="non-string key"):
        canonical_json({key: 1})


def test_non_string_key_in_nested_dict_reports_path():
    with pytest.raises(CanonError, match=r"\$\.a"):
        canonical_json({"a": {1: "x"}})
