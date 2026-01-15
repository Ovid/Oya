"""Tests for code metrics computation."""

from oya.generation.summaries import FileSummary, CodeMetrics


class TestComputeCodeMetrics:
    """Tests for compute_code_metrics function."""

    def test_computes_total_files(self):
        """Test total file count is computed correctly."""
        from oya.generation.metrics import compute_code_metrics

        summaries = [
            FileSummary(file_path="a.py", purpose="A", layer="api"),
            FileSummary(file_path="b.py", purpose="B", layer="domain"),
            FileSummary(file_path="c.py", purpose="C", layer="test"),
        ]
        contents = {"a.py": "x", "b.py": "y", "c.py": "z"}

        result = compute_code_metrics(summaries, contents)

        assert result.total_files == 3

    def test_computes_files_by_layer(self):
        """Test file counts per layer are computed correctly."""
        from oya.generation.metrics import compute_code_metrics

        summaries = [
            FileSummary(file_path="a.py", purpose="A", layer="api"),
            FileSummary(file_path="b.py", purpose="B", layer="api"),
            FileSummary(file_path="c.py", purpose="C", layer="domain"),
            FileSummary(file_path="d.py", purpose="D", layer="test"),
            FileSummary(file_path="e.py", purpose="E", layer="test"),
            FileSummary(file_path="f.py", purpose="F", layer="test"),
        ]
        contents = {s.file_path: "x" for s in summaries}

        result = compute_code_metrics(summaries, contents)

        assert result.files_by_layer["api"] == 2
        assert result.files_by_layer["domain"] == 1
        assert result.files_by_layer["test"] == 3

    def test_computes_lines_by_layer(self):
        """Test lines of code per layer are computed correctly."""
        from oya.generation.metrics import compute_code_metrics

        summaries = [
            FileSummary(file_path="a.py", purpose="A", layer="api"),
            FileSummary(file_path="b.py", purpose="B", layer="domain"),
        ]
        contents = {
            "a.py": "line1\nline2\nline3",  # 3 lines
            "b.py": "line1\nline2\nline3\nline4\nline5",  # 5 lines
        }

        result = compute_code_metrics(summaries, contents)

        assert result.lines_by_layer["api"] == 3
        assert result.lines_by_layer["domain"] == 5

    def test_computes_total_lines(self):
        """Test total lines of code is computed correctly."""
        from oya.generation.metrics import compute_code_metrics

        summaries = [
            FileSummary(file_path="a.py", purpose="A", layer="api"),
            FileSummary(file_path="b.py", purpose="B", layer="domain"),
        ]
        contents = {
            "a.py": "line1\nline2\nline3",  # 3 lines
            "b.py": "line1\nline2",  # 2 lines
        }

        result = compute_code_metrics(summaries, contents)

        assert result.total_lines == 5

    def test_handles_empty_summaries(self):
        """Test handling of empty summaries list."""
        from oya.generation.metrics import compute_code_metrics

        result = compute_code_metrics([], {})

        assert result.total_files == 0
        assert result.total_lines == 0
        assert result.files_by_layer == {}
        assert result.lines_by_layer == {}

    def test_handles_missing_content(self):
        """Test handling when file content is not available."""
        from oya.generation.metrics import compute_code_metrics

        summaries = [
            FileSummary(file_path="a.py", purpose="A", layer="api"),
            FileSummary(file_path="b.py", purpose="B", layer="api"),
        ]
        contents = {"a.py": "line1\nline2"}  # b.py missing

        result = compute_code_metrics(summaries, contents)

        assert result.total_files == 2
        assert result.lines_by_layer["api"] == 2  # Only a.py counted
        assert result.total_lines == 2

    def test_returns_code_metrics_type(self):
        """Test that result is a CodeMetrics instance."""
        from oya.generation.metrics import compute_code_metrics

        summaries = [FileSummary(file_path="a.py", purpose="A", layer="api")]
        contents = {"a.py": "x"}

        result = compute_code_metrics(summaries, contents)

        assert isinstance(result, CodeMetrics)
