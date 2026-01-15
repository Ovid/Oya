"""Tests for tech stack detection."""

from oya.generation.summaries import FileSummary


class TestLoadTechStackConfig:
    """Tests for loading tech stack configuration."""

    def test_load_config_returns_dict(self):
        """Test that config loads as a dictionary."""
        from oya.generation.techstack import load_techstack_config

        config = load_techstack_config()

        assert isinstance(config, dict)
        assert "libraries" in config

    def test_config_contains_known_libraries(self):
        """Test that config contains expected libraries."""
        from oya.generation.techstack import load_techstack_config

        config = load_techstack_config()
        libraries = config["libraries"]

        assert "fastapi" in libraries
        assert libraries["fastapi"]["language"] == "python"
        assert libraries["fastapi"]["category"] == "web_framework"

    def test_config_contains_perl_libraries(self):
        """Test that config contains Perl libraries."""
        from oya.generation.techstack import load_techstack_config

        config = load_techstack_config()
        libraries = config["libraries"]

        assert "mojolicious" in libraries
        assert libraries["mojolicious"]["language"] == "perl"
        assert "moose" in libraries
        assert libraries["moose"]["category"] == "object_system"


class TestDetectTechStack:
    """Tests for tech stack detection from file summaries."""

    def test_detect_single_library(self):
        """Test detection of a single known library."""
        from oya.generation.techstack import detect_tech_stack

        summaries = [
            FileSummary(
                file_path="app.py",
                purpose="Main app",
                layer="api",
                external_deps=["fastapi"],
            )
        ]

        result = detect_tech_stack(summaries)

        assert "python" in result
        assert "web_framework" in result["python"]
        assert "FastAPI" in result["python"]["web_framework"]

    def test_detect_multiple_libraries_same_language(self):
        """Test detection of multiple libraries from same language."""
        from oya.generation.techstack import detect_tech_stack

        summaries = [
            FileSummary(
                file_path="app.py",
                purpose="Main app",
                layer="api",
                external_deps=["fastapi", "sqlalchemy", "pytest"],
            )
        ]

        result = detect_tech_stack(summaries)

        assert "python" in result
        assert "FastAPI" in result["python"]["web_framework"]
        assert "SQLAlchemy" in result["python"]["database"]
        assert "pytest" in result["python"]["testing"]

    def test_detect_multiple_languages(self):
        """Test detection across multiple languages."""
        from oya.generation.techstack import detect_tech_stack

        summaries = [
            FileSummary(
                file_path="backend/app.py",
                purpose="Backend",
                layer="api",
                external_deps=["fastapi"],
            ),
            FileSummary(
                file_path="frontend/app.tsx",
                purpose="Frontend",
                layer="api",
                external_deps=["react", "axios"],
            ),
        ]

        result = detect_tech_stack(summaries)

        assert "python" in result
        assert "javascript" in result
        assert "FastAPI" in result["python"]["web_framework"]
        assert "React" in result["javascript"]["frontend"]

    def test_unknown_libraries_ignored(self):
        """Test that unknown libraries are silently ignored."""
        from oya.generation.techstack import detect_tech_stack

        summaries = [
            FileSummary(
                file_path="app.py",
                purpose="App",
                layer="api",
                external_deps=["fastapi", "some_unknown_lib", "another_unknown"],
            )
        ]

        result = detect_tech_stack(summaries)

        assert "python" in result
        assert "FastAPI" in result["python"]["web_framework"]

    def test_deduplication(self):
        """Test that duplicate libraries are deduplicated."""
        from oya.generation.techstack import detect_tech_stack

        summaries = [
            FileSummary(file_path="a.py", purpose="A", layer="api", external_deps=["fastapi"]),
            FileSummary(file_path="b.py", purpose="B", layer="api", external_deps=["fastapi"]),
            FileSummary(file_path="c.py", purpose="C", layer="api", external_deps=["fastapi"]),
        ]

        result = detect_tech_stack(summaries)

        assert result["python"]["web_framework"].count("FastAPI") == 1

    def test_empty_summaries(self):
        """Test handling of empty summaries list."""
        from oya.generation.techstack import detect_tech_stack

        result = detect_tech_stack([])

        assert result == {}

    def test_no_external_deps(self):
        """Test handling of summaries with no external deps."""
        from oya.generation.techstack import detect_tech_stack

        summaries = [
            FileSummary(file_path="app.py", purpose="App", layer="api", external_deps=[])
        ]

        result = detect_tech_stack(summaries)

        assert result == {}
