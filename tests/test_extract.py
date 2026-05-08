from __future__ import annotations

import pytest

from agent.extract import ExtractionError, extract


def test_extract_two_blocks():
    resp = """sure, here:

```python
# solution.py
def add(a, b):
    return a + b
```

```python
# test_solution.py
from solution import add

def test_add():
    assert add(1, 2) == 3
```
"""
    out = extract(resp)
    assert "def add" in out.code
    assert "def test_add" in out.tests


def test_extract_fails_on_one_block():
    with pytest.raises(ExtractionError):
        extract("```python\ndef add(a,b): return a+b\n```")


def test_extract_fails_on_empty():
    with pytest.raises(ExtractionError):
        extract("")


def test_extract_orders_by_test_signature():
    resp = """```python
def test_thing():
    assert True
```

```python
def thing():
    return 1
```
"""
    out = extract(resp)
    assert "def thing" in out.code
    assert "test_thing" in out.tests
