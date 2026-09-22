from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .models import InvariantStatus


@dataclass(frozen=True)
class Invariant:
    id: str
    description: str
    evaluate: Callable[[dict[str, Any]], bool]

    def check(self, state: dict[str, Any]) -> InvariantStatus:
        return InvariantStatus.PASS if self.evaluate(state) else InvariantStatus.FAIL


PAYMENT_ONCE = Invariant(
    id="PAY-001",
    description="A cart can produce at most one successful payment",
    evaluate=lambda state: state["payment_count"] <= 1,
)

