import pytest
from drama_llm import JsonExtractError, extract_json


def test_extract_raw_object() -> None:
    assert extract_json('{"ok": true, "n": 1}') == {"ok": True, "n": 1}


def test_extract_fenced_json() -> None:
    text = """here you go
```json
{"action": "pass", "scores": {"coherence": 8}}
```
thanks
"""
    assert extract_json(text)["action"] == "pass"


def test_extract_prose_wrapped_array() -> None:
    assert extract_json("prefix [1, 2, 3] suffix") == [1, 2, 3]


def test_extract_empty_raises() -> None:
    with pytest.raises(JsonExtractError):
        extract_json("   ")
    with pytest.raises(JsonExtractError):
        extract_json("no json here")
