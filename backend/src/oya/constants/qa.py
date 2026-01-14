"""Q&A service configuration.

These settings control the behavior of the Q&A feature, which allows users
to ask natural language questions about the codebase and receive answers
based on the generated wiki documentation.
"""

# =============================================================================
# Token Budgets
# =============================================================================
# The Q&A system builds prompts by combining the user's question with relevant
# context from the wiki. These limits prevent prompts from exceeding LLM context
# windows. MAX_CONTEXT_TOKENS caps the total context size, while MAX_RESULT_TOKENS
# prevents any single document from dominating. Values are in tokens (roughly 4
# characters per token for English text).

MAX_CONTEXT_TOKENS = 6000
MAX_RESULT_TOKENS = 1500

# =============================================================================
# Confidence Scoring
# =============================================================================
# Answers are assigned a confidence level (high/medium/low) based on how well
# search results match the question. This uses vector similarity distances where
# 0.0 = perfect match and 1.0 = completely unrelated. "High" confidence requires
# multiple strong matches below the HIGH threshold. "Medium" requires at least one
# decent match below the MEDIUM threshold. Otherwise, confidence is "low".

HIGH_CONFIDENCE_THRESHOLD = 0.3
MEDIUM_CONFIDENCE_THRESHOLD = 0.6
STRONG_MATCH_THRESHOLD = 0.5
MIN_STRONG_MATCHES_FOR_HIGH = 3
