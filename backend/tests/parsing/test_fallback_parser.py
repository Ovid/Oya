"""Tests for fallback parser synopsis extraction."""

from oya.parsing.fallback_parser import FallbackParser


def test_extract_rust_doc_examples():
    """Should extract code from Rust //! # Examples sections."""
    code = """//! Email validation utilities.
//!
//! # Examples
//!
//! ```
//! use mylib::validate_email;
//!
//! let is_valid = validate_email("user@example.com");
//! ```

pub fn validate_email(email: &str) -> bool {
    email.contains('@')
}
"""
    parser = FallbackParser()
    result = parser.parse_string(code, "email.rs")

    expected = """use mylib::validate_email;

let is_valid = validate_email("user@example.com");"""

    assert result.file.synopsis == expected


def test_no_rust_synopsis_without_examples_section():
    """Should return None when Rust file has no Examples section."""
    code = """//! Email validation utilities.

pub fn validate_email(email: &str) -> bool {
    true
}
"""
    parser = FallbackParser()
    result = parser.parse_string(code, "email.rs")
    assert result.file.synopsis is None
