"""Wiki generation configuration.

These settings control how the wiki is generated from source code, including
LLM parameters for content synthesis and token estimation.
"""

# =============================================================================
# LLM Parameters
# =============================================================================
# Temperature controls randomness in LLM output. Lower values (0.0-0.3) produce
# more deterministic, focused output suitable for structured documentation.
# Higher values (0.7-1.0) produce more creative, varied output.

SYNTHESIS_TEMPERATURE = 0.3

# =============================================================================
# Token Estimation
# =============================================================================
# When chunking code for processing, we estimate token counts from character
# counts. TOKENS_PER_CHAR is a rough multiplier (code tends to tokenize less
# efficiently than prose). DEFAULT_CONTEXT_LIMIT caps how much content is
# sent to the LLM for synthesis operations.

TOKENS_PER_CHAR = 0.25
DEFAULT_CONTEXT_LIMIT = 100_000

# =============================================================================
# Chunking
# =============================================================================
# Large files are split into chunks for processing. MAX_CHUNK_TOKENS sets the
# target chunk size. CHUNK_OVERLAP_LINES adds redundancy between chunks so
# context isn't lost at boundaries.

MAX_CHUNK_TOKENS = 1000
CHUNK_OVERLAP_LINES = 5
