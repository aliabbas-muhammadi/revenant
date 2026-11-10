import hashlib

import pytest

from revenant.canon import CanonError, canonical_json, state_hash


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


GOLDEN_STATE = {
    "step": 3,
    "name": "caf\u00e9",
    "items": [1, 2.5, None, True],
    "nested": {"b": 1, "a": []},
}
GOLDEN_HASH = "2a114b98d20c347da264af430d7733d3f28b76bc19e717a6992fa1ba7a81cd58"


def test_state_hash_golden():
    assert state_hash(GOLDEN_STATE) == GOLDEN_HASH


def test_state_hash_is_hex_sha256_of_canonical_bytes():
    obj = {"b": 1, "a": 2}
    assert state_hash(obj) == hashlib.sha256(canonical_json(obj)).hexdigest()
    assert len(state_hash(obj)) == 64


def test_volatile_field_excluded():
    a = {"meta": {"ts": 1, "id": "x"}, "n": 1}
    b = {"meta": {"ts": 999, "id": "x"}, "n": 1}
    assert state_hash(a) != state_hash(b)
    assert state_hash(a, ["meta.ts"]) == state_hash(b, ["meta.ts"])


def test_volatile_field_only_matches_exact_path():
    a = {"meta": {"ts": 1}, "ts": 1}
    b = {"meta": {"ts": 2}, "ts": 1}
    assert state_hash(a, ["ts"]) != state_hash(b, ["ts"])


def test_volatile_field_inside_list_of_dicts():
    a = {"calls": [{"tool": "x", "ms": 5}, {"tool": "y", "ms": 7}]}
    b = {"calls": [{"tool": "x", "ms": 50}, {"tool": "y", "ms": 70}]}
    assert state_hash(a) != state_hash(b)
    assert state_hash(a, ["calls.ms"]) == state_hash(b, ["calls.ms"])


def test_volatile_field_deep_and_non_mutating():
    a = {"a": {"b": {"c": 1, "keep": 2}}}
    before = repr(a)
    assert state_hash(a, ["a.b.c"]) == state_hash({"a": {"b": {"keep": 2}}})
    assert repr(a) == before


def test_volatile_field_absent_is_noop():
    assert state_hash({"a": 1}, ["nope.here"]) == state_hash({"a": 1})


def test_wildcard_matches_at_any_depth():
    a = {"ts": 1, "x": {"ts": 2, "y": [{"ts": 3, "k": 1}]}}
    b = {"ts": 9, "x": {"ts": 8, "y": [{"ts": 7, "k": 1}]}}
    assert state_hash(a) != state_hash(b)
    assert state_hash(a, ["*.ts"]) == state_hash(b, ["*.ts"])


def test_wildcard_leaves_other_keys_alone():
    a = {"x": {"ts": 1, "keep": 1}}
    b = {"x": {"ts": 1, "keep": 2}}
    assert state_hash(a, ["*.ts"]) != state_hash(b, ["*.ts"])


def test_wildcard_with_multi_segment_suffix():
    a = {"a": {"meta": {"ts": 1}}, "meta": {"ts": 5}, "other": {"ts": 1}}
    b = {"a": {"meta": {"ts": 2}}, "meta": {"ts": 6}, "other": {"ts": 2}}
    assert state_hash(a, ["*.meta.ts"]) == state_hash(
        {**b, "other": {"ts": 1}}, ["*.meta.ts"]
    )
    assert state_hash(a, ["*.meta.ts"]) != state_hash(b, ["*.meta.ts"])


def test_int_and_float_are_distinct():
    assert canonical_json(1) == b"1"
    assert canonical_json(1.0) == b"1.0"
    assert state_hash({"n": 1}) != state_hash({"n": 1.0})


def test_bool_does_not_collide_with_int():
    assert canonical_json(True) == b"true"
    assert state_hash([True]) != state_hash([1])
