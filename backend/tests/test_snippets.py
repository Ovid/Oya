"""Tests for call-site snippet extraction."""


class TestIsTestFile:
    """Tests for is_test_file detection."""

    def test_test_prefix(self):
        """Detects test_*.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("test_something.py") is True
        assert is_test_file("src/test_module.py") is True

    def test_test_suffix(self):
        """Detects *_test.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("something_test.py") is True
        assert is_test_file("module_test.py") is True

    def test_spec_suffix(self):
        """Detects *_spec.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("something_spec.py") is True

    def test_tests_directory(self):
        """Detects files in tests/ directories."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("tests/test_foo.py") is True
        assert is_test_file("tests/helpers.py") is True
        assert is_test_file("src/tests/utils.py") is True

    def test_test_directory(self):
        """Detects files in test/ directories."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("test/test_bar.py") is True

    def test_spec_directory(self):
        """Detects files in spec/ directories."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("spec/foo_spec.py") is True

    def test_dunder_tests_directory(self):
        """Detects files in __tests__/ directories (JS convention)."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("src/__tests__/component.test.js") is True

    def test_conftest(self):
        """Detects conftest.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("conftest.py") is True
        assert is_test_file("tests/conftest.py") is True

    def test_fixtures(self):
        """Detects fixtures.py files."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("fixtures.py") is True

    def test_production_files(self):
        """Does not flag production files as tests."""
        from oya.generation.snippets import is_test_file

        assert is_test_file("main.py") is False
        assert is_test_file("src/handler.py") is False
        assert is_test_file("api/routes.py") is False
        assert is_test_file("utils/testing_utils.py") is False  # "testing" in name but not a test
