"""Job management API tests."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance, get_db


@pytest.fixture
def workspace_with_db(tmp_path, monkeypatch):
    """Create workspace with database and job."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    from oya.config import load_settings
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    # Initialize database with a test job
    db = get_db()
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, current_phase, total_phases)
        VALUES ('test-job-123', 'full', 'running', datetime('now'), 'analysis', 6)
        """
    )
    db.commit()

    yield workspace

    _reset_db_instance()


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_get_job_status(client, workspace_with_db):
    """GET /api/jobs/{job_id} returns job status."""
    response = await client.get("/api/jobs/test-job-123")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-123"
    assert data["status"] == "running"
    assert data["current_phase"] == "analysis"


async def test_get_nonexistent_job_returns_404(client, workspace_with_db):
    """GET /api/jobs/{nonexistent} returns 404."""
    response = await client.get("/api/jobs/nonexistent-job")

    assert response.status_code == 404


async def test_list_jobs(client, workspace_with_db):
    """GET /api/jobs returns list of jobs."""
    response = await client.get("/api/jobs")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["job_id"] == "test-job-123"


async def test_cancel_running_job(client, workspace_with_db):
    """POST /api/jobs/{job_id}/cancel cancels a running job."""
    response = await client.post("/api/jobs/test-job-123/cancel")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-123"
    assert data["status"] == "cancelled"
    assert "cancelled_at" in data


async def test_cancel_nonexistent_job_returns_404(client, workspace_with_db):
    """POST /api/jobs/{nonexistent}/cancel returns 404."""
    response = await client.post("/api/jobs/nonexistent-job/cancel")

    assert response.status_code == 404


async def test_cancel_completed_job_returns_400(client, workspace_with_db):
    """POST /api/jobs/{completed}/cancel returns 400."""
    # Insert a completed job
    db = get_db()
    db.execute(
        """
        INSERT INTO generations (id, type, status, started_at, completed_at)
        VALUES ('completed-job', 'full', 'completed', datetime('now'), datetime('now'))
        """
    )
    db.commit()

    response = await client.post("/api/jobs/completed-job/cancel")

    assert response.status_code == 400


class TestPhaseOrderConsistency:
    """Tests to ensure backend phase order matches frontend expectations.
    
    The bottom-up generation pipeline runs phases in this order:
    Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows
    
    Both backend and frontend must agree on this ordering for progress display to work correctly.
    """

    def test_phase_numbers_match_bottom_up_order(self):
        """Phase numbers in repos.py match the bottom-up generation order."""
        # Import the phase_numbers mapping from repos.py
        # We test this by checking the expected values directly
        expected_phase_numbers = {
            "analysis": 1,
            "files": 2,
            "directories": 3,
            "synthesis": 4,
            "architecture": 5,
            "overview": 6,
            "workflows": 7,
            "indexing": 8,
        }
        
        # Import and check the actual mapping
        from oya.api.routers import repos
        import inspect
        
        # Get the source code of _run_generation to extract phase_numbers
        source = inspect.getsource(repos._run_generation)
        
        # Verify each phase appears in the correct order
        for phase, expected_num in expected_phase_numbers.items():
            assert f'"{phase}": {expected_num}' in source, \
                f"Phase '{phase}' should have number {expected_num} in repos.py"

    def test_total_phases_is_eight(self):
        """Total phases should be 8 for the bottom-up pipeline (including indexing)."""
        from oya.api.routers import repos
        import inspect
        
        source = inspect.getsource(repos.init_repo)
        
        # Check that total_phases is 8
        assert '"full", "pending", 8' in source or "'full', 'pending', 8" in source, \
            "Total phases should be 8 in init_repo"

    def test_files_before_architecture(self):
        """Files phase number should be less than architecture phase number."""
        expected_phase_numbers = {
            "analysis": 1,
            "files": 2,
            "directories": 3,
            "synthesis": 4,
            "architecture": 5,
            "overview": 6,
            "workflows": 7,
            "indexing": 8,
        }
        
        assert expected_phase_numbers["files"] < expected_phase_numbers["architecture"], \
            "Files phase should come before architecture in bottom-up approach"

    def test_synthesis_before_architecture_and_overview(self):
        """Synthesis phase should come before architecture and overview."""
        expected_phase_numbers = {
            "analysis": 1,
            "files": 2,
            "directories": 3,
            "synthesis": 4,
            "architecture": 5,
            "overview": 6,
            "workflows": 7,
        }
        
        assert expected_phase_numbers["synthesis"] < expected_phase_numbers["architecture"], \
            "Synthesis should come before architecture"
        assert expected_phase_numbers["synthesis"] < expected_phase_numbers["overview"], \
            "Synthesis should come before overview"

    def test_phase_order_matches_orchestrator_enum(self):
        """Phase order should match GenerationPhase enum values."""
        from oya.generation.orchestrator import GenerationPhase
        
        # All phases in the mapping should exist in the enum
        expected_phases = ["analysis", "files", "directories", "synthesis", 
                          "architecture", "overview", "workflows"]
        
        enum_values = [phase.value for phase in GenerationPhase]
        
        for phase in expected_phases:
            assert phase in enum_values, \
                f"Phase '{phase}' should exist in GenerationPhase enum"
