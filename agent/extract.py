from __future__ import annotations

import re
from dataclasses import dataclass


class ExtractionError(ValueError):
    """Raised when a model response cannot be parsed into code + tests."""


@dataclass(frozen=True)
class Extracted:
    code: str
    tests: str


_FENCE_RE = re.compile(
    r"```(?:python|py)?\s*\n(?P<body>.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract(response: str) -> Extracted:
    if not response or not response.strip():
        raise ExtractionError("model response is empty")

    blocks = [m.group("body") for m in _FENCE_RE.finditer(response)]
    blocks = [b.strip("\n") for b in blocks if b.strip()]

    code_block: str | None = None
    test_block: str | None = None

    for b in blocks:
        if _looks_like_tests(b):
            if test_block is None:
                test_block = b
        else:
            if code_block is None:
                code_block = b

    if code_block is None or test_block is None:
        if len(blocks) >= 2:
            code_block = code_block or blocks[0]
            test_block = test_block or blocks[1]
        else:
            raise ExtractionError(
                f"expected at least two code blocks (solution + tests); found {len(blocks)}"
            )

    return Extracted(code=code_block.rstrip() + "\n", tests=test_block.rstrip() + "\n")


def _looks_like_tests(body: str) -> bool:
    head = body.lstrip().splitlines()[:3]
    head_text = "\n".join(head).lower()
    if "# test_solution.py" in head_text or "test_solution.py" in head_text:
        return True
    return bool(re.search(r"^\s*def\s+test_\w+\s*\(", body, re.MULTILINE))
