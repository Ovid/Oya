"""File filtering and processing configuration.

These settings control which files are included in wiki generation and
how they're processed. Large or binary files are excluded to keep the
wiki focused on human-readable source code.
"""

# =============================================================================
# Size Limits
# =============================================================================
# Files larger than MAX_FILE_SIZE_KB are skipped during generation. This
# prevents huge generated files, minified bundles, or data files from
# bloating the wiki and consuming excessive LLM tokens.

MAX_FILE_SIZE_KB = 500

# =============================================================================
# Binary Detection
# =============================================================================
# To detect binary files, we read the first N bytes and check for null
# characters. Binary files are always excluded from generation.

BINARY_CHECK_BYTES = 1024

# =============================================================================
# Minified/Generated File Detection
# =============================================================================
# Files with average line length exceeding this threshold are considered
# minified or generated and excluded from analysis. Minified files have
# extremely long lines (often entire file on one line).

MINIFIED_AVG_LINE_LENGTH = 500

# =============================================================================
# Concurrency
# =============================================================================
# Number of files to process in parallel during generation. Lower values
# are safer for local models (Ollama) which may have limited capacity.
# Cloud APIs (OpenAI, Anthropic) can handle higher concurrency.

PARALLEL_FILE_LIMIT_LOCAL = 2
PARALLEL_FILE_LIMIT_CLOUD = 10
