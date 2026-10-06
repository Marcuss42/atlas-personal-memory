from ..logger import debug_event
from .query.query_router import MemoryQueryRouter
from .query.query_executor import MemoryQueryExecutor


class MemoryRetriever:
    def __init__(self, memory):
        self.memory = memory
        self.router = MemoryQueryRouter()
        self.executor = MemoryQueryExecutor(
            memory
        )

    def retrieve(
        self,
        query,
        recent_messages=None
    ):
        debug_event(
            "RETRIEVER_START",
            query=query
        )

        plan = self.router.route(
            query
        )

        debug_event(
            "MEMORY_QUERY_PLAN",
            action=plan.action,
            scope=plan.scope,
            query=plan.query,
            entity_hint=plan.entity_hint,
            predicate=plan.predicate,
            object_hint=plan.object_hint,
            relation_direction=plan.relation_direction,
            limit=plan.limit
        )

        result = self.executor.execute(
            plan
        )

        debug_event(
            "RETRIEVER_RESULT",
            action=plan.action,
            scope=plan.scope,
            query=plan.query,
            entity_hint=plan.entity_hint,
            predicate=plan.predicate,
            object_hint=plan.object_hint,
            relation_direction=plan.relation_direction,
            results_count=len(result),
            results=result
        )

        return result