from dataclasses import dataclass
from typing import Any, Protocol


class AgentStep(Protocol):
    name: str

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run one agent step and return data to merge into the workflow context."""


@dataclass(frozen=True)
class DeterministicAgent:
    name: str

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return context
