import pytest


def test_langgraph_extra_is_importable():
    pytest.importorskip("langgraph.graph")
    pytest.importorskip("langgraph.checkpoint.sqlite")
