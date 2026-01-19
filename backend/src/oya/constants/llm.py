"""LLM client configuration.

Default parameters for LLM API calls. These can be overridden per-call
but provide sensible defaults for most use cases.
"""

# =============================================================================
# Generation Defaults
# =============================================================================
# MAX_TOKENS caps response length to control costs and ensure responses complete.
# DEFAULT_TEMPERATURE balances creativity and consistency (0.7 is a common default).
# JSON_TEMPERATURE is lower for structured output where consistency matters more.

MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.7
JSON_TEMPERATURE = 0.3
