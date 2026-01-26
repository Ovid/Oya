"""Query classification for mode-specific retrieval."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oya.llm.client import LLMClient

logger = logging.getLogger(__name__)


class QueryMode(Enum):
    """Query classification modes."""

    DIAGNOSTIC = "diagnostic"
    EXPLORATORY = "exploratory"
    ANALYTICAL = "analytical"
    CONCEPTUAL = "conceptual"


@dataclass
class ClassificationResult:
    """Result of query classification."""

    mode: QueryMode
    reasoning: str
    scope: str | None


CLASSIFICATION_SYSTEM_PROMPT = """You are a query classifier for a codebase Q&A system.
Your job is to determine the best retrieval strategy for answering the user's question.

## Why This Matters

Different questions need different retrieval approaches:

- CONCEPTUAL questions ("what does X do?") are answered well by high-level
  documentation and wiki summaries.

- DIAGNOSTIC questions ("why is X failing?") require tracing errors back to
  root causes. The symptoms described in the query often have LOW semantic
  similarity to the actual cause. We need to find error sites in code and
  walk the call graph backward to find state mutations or side effects.

- EXPLORATORY questions ("trace the auth flow") require following execution
  paths forward through the codebase. We need to find entry points and walk
  the call graph to show how components connect.

- ANALYTICAL questions ("what are the architectural flaws?") require examining
  code structure, dependencies, and known issues. We need structural analysis,
  not just text search.

## Classification Rules

DIAGNOSTIC - Choose when:
  - Query contains error messages, exception types, or stack traces
  - Query describes unexpected behavior ("X happens when it should Y")
  - Query asks WHY something is broken, failing, or not working
  - Query mentions specific error codes or status codes

EXPLORATORY - Choose when:
  - Query asks to trace, follow, or walk through code paths
  - Query asks how components connect or call each other
  - Query asks about execution order or data flow
  - Query wants to understand a sequence of operations

ANALYTICAL - Choose when:
  - Query asks about architecture, structure, or design
  - Query asks about code quality, flaws, or problems
  - Query asks about dependencies, coupling, or cohesion
  - Query asks for assessment or evaluation of code

CONCEPTUAL - Choose when:
  - Query asks what something does or how to use it
  - Query asks for explanation of a feature or module
  - Query is a general question about functionality
  - None of the above categories clearly fit

## Response Format

Respond with a JSON object:
{
  "mode": "DIAGNOSTIC" | "EXPLORATORY" | "ANALYTICAL" | "CONCEPTUAL",
  "reasoning": "<one sentence explaining why>",
  "scope": "<specific part of codebase if mentioned, otherwise null>"
}"""


class QueryClassifier:
    """Classifies queries to determine retrieval strategy."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    async def classify(self, query: str) -> ClassificationResult:
        """Classify a query into a retrieval mode."""
        try:
            response = await self.llm.complete(
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                user_prompt=f"Classify this question: {query}",
                temperature=0.0,
                max_tokens=200,
            )

            # Parse JSON response
            result = json.loads(response.content)
            mode = QueryMode(result["mode"].lower())

            return ClassificationResult(
                mode=mode,
                reasoning=result.get("reasoning", ""),
                scope=result.get("scope"),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse classification response: {e}")
            return ClassificationResult(
                mode=QueryMode.CONCEPTUAL,
                reasoning="Default classification due to parsing error",
                scope=None,
            )
