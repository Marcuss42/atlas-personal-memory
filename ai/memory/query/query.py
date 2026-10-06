from dataclasses import dataclass
from typing import Literal


QueryAction = Literal[
    "search",
    "list",
    "count",
    "related"
]

QueryScope = Literal[
    "self",
    "entity",
    "global"
]

RelationDirection = Literal[
    "subject",
    "object",
    "both"
]


@dataclass(frozen=True)
class MemoryQueryPlan:
    action: QueryAction
    scope: QueryScope
    query: str
    entity_hint: str | None = None
    predicate: str | None = None
    object_hint: str | None = None
    relation_direction: RelationDirection = "both"
    limit: int = 20