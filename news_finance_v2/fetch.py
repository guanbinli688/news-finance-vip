from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FetchResult:
    name: str
    status: str
    url: str = ""
    kind: str = ""
    text: str = ""
    error_type: str = ""
    message: str = ""
    core: bool = False


def source_coverage(results: list[FetchResult]) -> float:
    return sum(r.status == "SUCCESS" for r in results) / len(results) if results else 0.0
