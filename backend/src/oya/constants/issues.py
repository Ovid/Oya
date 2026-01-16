"""Issue detection configuration.

These settings control the code issue detection feature, which identifies
potential bugs, security concerns, and design flaws during wiki generation.
"""

# =============================================================================
# Issue Categories
# =============================================================================
# Categories represent broad classes of issues. Each category has specific
# patterns the LLM looks for during analysis.

ISSUE_CATEGORIES = frozenset(["security", "reliability", "maintainability"])

# Category descriptions for LLM prompt
CATEGORY_DESCRIPTIONS = {
    "security": "Injection vulnerabilities, hardcoded secrets, missing auth, unsafe deserialization",
    "reliability": "Unhandled errors, race conditions, resource leaks, null pointer risks",
    "maintainability": "God classes, circular deps, code duplication, missing abstractions",
}

# =============================================================================
# Issue Severities
# =============================================================================
# Severities indicate urgency. "problem" means likely bug or security hole.
# "suggestion" means improvement opportunity but not urgent.

ISSUE_SEVERITIES = frozenset(["problem", "suggestion"])

SEVERITY_DESCRIPTIONS = {
    "problem": "Likely bug or security hole that needs attention",
    "suggestion": "Improvement opportunity, not urgent",
}

# =============================================================================
# Q&A Integration
# =============================================================================
# Keywords that trigger issue-aware Q&A responses

ISSUE_QUERY_KEYWORDS = frozenset([
    "bug",
    "bugs",
    "issue",
    "issues",
    "problem",
    "problems",
    "security",
    "vulnerability",
    "vulnerabilities",
    "code quality",
    "technical debt",
    "tech debt",
    "what's wrong",
    "whats wrong",
    "concerns",
    "risks",
    "flaws",
])
