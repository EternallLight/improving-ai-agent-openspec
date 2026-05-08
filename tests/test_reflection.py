from __future__ import annotations

from agent.reflection import StructuredReflection, parse_structured_reflection


def test_parse_well_formed_json_block():
    raw = """Here you go:
```json
{
  "error_type": "AssertionError",
  "root_cause_summary": "wrong operator used",
  "code_or_assumptions": "return a - b",
  "next_hypothesis": "use + instead"
}
```
"""
    s = parse_structured_reflection(raw)
    assert isinstance(s, StructuredReflection)
    assert s.error_type == "AssertionError"
    assert "operator" in s.root_cause_summary
    assert s.next_hypothesis == "use + instead"


def test_parse_bare_json():
    raw = '{"error_type":"ImportError","root_cause_summary":"missing module","code_or_assumptions":"import x","next_hypothesis":"install x"}'
    s = parse_structured_reflection(raw)
    assert s.error_type == "ImportError"


def test_parse_failure_returns_fallback():
    s = parse_structured_reflection("just plain text, no JSON")
    assert s.error_type == "ParseError"
    assert "just plain text" in s.root_cause_summary
    assert s.next_hypothesis  # non-empty


def test_parse_empty_returns_fallback():
    s = parse_structured_reflection("")
    assert s.error_type == "ParseError"
    assert s.root_cause_summary


def test_parse_missing_fields_returns_fallback():
    raw = '```json\n{"error_type":"X"}\n```'
    s = parse_structured_reflection(raw)
    assert s.error_type == "ParseError"
