# Phase 6 Overview Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enrich SynthesisMap with entry points, tech stack, code metrics, and layer interactions to generate more accurate, code-derived overview pages.

**Architecture:** Add four new fields to SynthesisMap computed during Phase 4 synthesis. Tech stack detection uses a YAML config mapping libraries to categories. Entry points reuse existing WorkflowDiscovery. Layer interactions are LLM-generated via the existing synthesis prompt. Overview prompt updated to use all new context.

**Tech Stack:** Python 3.11+, pytest, YAML config, existing LLM client

---

## Task 1: Add EntryPointInfo Dataclass

**Files:**
- Modify: `backend/src/oya/generation/summaries.py`
- Test: `backend/tests/test_summaries.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_summaries.py`:

```python
class TestEntryPointInfo:
    """Tests for EntryPointInfo dataclass."""

    def test_entry_point_info_creation(self):
        """Test EntryPointInfo can be created with required fields."""
        from oya.generation.summaries import EntryPointInfo

        ep = EntryPointInfo(
            name="create_user",
            entry_type="api_route",
            file="api/routers/users.py",
            description="/users POST",
        )

        assert ep.name == "create_user"
        assert ep.entry_type == "api_route"
        assert ep.file == "api/routers/users.py"
        assert ep.description == "/users POST"

    def test_entry_point_info_to_dict(self):
        """Test EntryPointInfo serializes to dict."""
        from oya.generation.summaries import EntryPointInfo

        ep = EntryPointInfo(
            name="main",
            entry_type="main_function",
            file="src/main.py",
            description="",
        )

        data = ep.to_dict()

        assert data == {
            "name": "main",
            "entry_type": "main_function",
            "file": "src/main.py",
            "description": "",
        }

    def test_entry_point_info_from_dict(self):
        """Test EntryPointInfo deserializes from dict."""
        from oya.generation.summaries import EntryPointInfo

        data = {
            "name": "cli_init",
            "entry_type": "cli_command",
            "file": "cli/commands.py",
            "description": "init",
        }

        ep = EntryPointInfo.from_dict(data)

        assert ep.name == "cli_init"
        assert ep.entry_type == "cli_command"
        assert ep.file == "cli/commands.py"
        assert ep.description == "init"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestEntryPointInfo -v`

Expected: FAIL with "cannot import name 'EntryPointInfo'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/summaries.py` after `ComponentInfo` class:

```python
@dataclass
class EntryPointInfo:
    """Information about an entry point in the codebase.

    Represents a CLI command, API route, or main function that serves
    as a starting point for users interacting with the system.

    Attributes:
        name: The entry point name (e.g., function name).
        entry_type: Type of entry point (cli_command, api_route, main_function).
        file: Path to the file containing this entry point.
        description: Route path, CLI command name, or other descriptor.
    """

    name: str
    entry_type: str
    file: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "entry_type": self.entry_type,
            "file": self.file,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntryPointInfo":
        """Deserialize from dictionary."""
        return cls(
            name=data.get("name", ""),
            entry_type=data.get("entry_type", ""),
            file=data.get("file", ""),
            description=data.get("description", ""),
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestEntryPointInfo -v`

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/summaries.py backend/tests/test_summaries.py
git commit -m "feat: add EntryPointInfo dataclass for entry point tracking"
```

---

## Task 2: Add CodeMetrics Dataclass

**Files:**
- Modify: `backend/src/oya/generation/summaries.py`
- Test: `backend/tests/test_summaries.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_summaries.py`:

```python
class TestCodeMetrics:
    """Tests for CodeMetrics dataclass."""

    def test_code_metrics_creation(self):
        """Test CodeMetrics can be created with all fields."""
        from oya.generation.summaries import CodeMetrics

        metrics = CodeMetrics(
            total_files=50,
            files_by_layer={"api": 10, "domain": 20, "infrastructure": 15, "utility": 5},
            lines_by_layer={"api": 1000, "domain": 3000, "infrastructure": 2000, "utility": 500},
            total_lines=6500,
        )

        assert metrics.total_files == 50
        assert metrics.files_by_layer["domain"] == 20
        assert metrics.lines_by_layer["domain"] == 3000
        assert metrics.total_lines == 6500

    def test_code_metrics_to_dict(self):
        """Test CodeMetrics serializes to dict."""
        from oya.generation.summaries import CodeMetrics

        metrics = CodeMetrics(
            total_files=10,
            files_by_layer={"api": 5, "domain": 5},
            lines_by_layer={"api": 500, "domain": 500},
            total_lines=1000,
        )

        data = metrics.to_dict()

        assert data == {
            "total_files": 10,
            "files_by_layer": {"api": 5, "domain": 5},
            "lines_by_layer": {"api": 500, "domain": 500},
            "total_lines": 1000,
        }

    def test_code_metrics_from_dict(self):
        """Test CodeMetrics deserializes from dict."""
        from oya.generation.summaries import CodeMetrics

        data = {
            "total_files": 25,
            "files_by_layer": {"test": 10, "utility": 15},
            "lines_by_layer": {"test": 2000, "utility": 1500},
            "total_lines": 3500,
        }

        metrics = CodeMetrics.from_dict(data)

        assert metrics.total_files == 25
        assert metrics.files_by_layer["test"] == 10
        assert metrics.total_lines == 3500
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestCodeMetrics -v`

Expected: FAIL with "cannot import name 'CodeMetrics'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/summaries.py` after `EntryPointInfo` class:

```python
@dataclass
class CodeMetrics:
    """Aggregated code metrics for the codebase.

    Provides quantitative information about project scale and distribution
    of code across architectural layers.

    Attributes:
        total_files: Total number of analyzed files.
        files_by_layer: Count of files per architectural layer.
        lines_by_layer: Lines of code per architectural layer.
        total_lines: Total lines of code across all files.
    """

    total_files: int
    files_by_layer: dict[str, int]
    lines_by_layer: dict[str, int]
    total_lines: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_files": self.total_files,
            "files_by_layer": self.files_by_layer,
            "lines_by_layer": self.lines_by_layer,
            "total_lines": self.total_lines,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodeMetrics":
        """Deserialize from dictionary."""
        return cls(
            total_files=data.get("total_files", 0),
            files_by_layer=data.get("files_by_layer", {}),
            lines_by_layer=data.get("lines_by_layer", {}),
            total_lines=data.get("total_lines", 0),
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestCodeMetrics -v`

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/summaries.py backend/tests/test_summaries.py
git commit -m "feat: add CodeMetrics dataclass for code statistics"
```

---

## Task 3: Extend SynthesisMap with New Fields

**Files:**
- Modify: `backend/src/oya/generation/summaries.py`
- Test: `backend/tests/test_summaries.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_summaries.py`:

```python
class TestSynthesisMapExtended:
    """Tests for extended SynthesisMap fields."""

    def test_synthesis_map_has_new_fields(self):
        """Test SynthesisMap includes entry_points, tech_stack, metrics, layer_interactions."""
        from oya.generation.summaries import (
            SynthesisMap,
            EntryPointInfo,
            CodeMetrics,
        )

        entry_points = [
            EntryPointInfo(name="main", entry_type="main_function", file="main.py", description="")
        ]
        tech_stack = {"python": {"web_framework": ["FastAPI"]}}
        metrics = CodeMetrics(
            total_files=10,
            files_by_layer={"api": 5, "domain": 5},
            lines_by_layer={"api": 500, "domain": 500},
            total_lines=1000,
        )

        sm = SynthesisMap(
            entry_points=entry_points,
            tech_stack=tech_stack,
            metrics=metrics,
            layer_interactions="API layer calls domain services directly.",
        )

        assert len(sm.entry_points) == 1
        assert sm.entry_points[0].name == "main"
        assert sm.tech_stack["python"]["web_framework"] == ["FastAPI"]
        assert sm.metrics.total_files == 10
        assert sm.layer_interactions == "API layer calls domain services directly."

    def test_synthesis_map_json_roundtrip_with_new_fields(self):
        """Test SynthesisMap serialization includes new fields."""
        from oya.generation.summaries import (
            SynthesisMap,
            EntryPointInfo,
            CodeMetrics,
            LayerInfo,
        )

        original = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP handlers", directories=[], files=[])},
            key_components=[],
            dependency_graph={},
            project_summary="Test project",
            entry_points=[
                EntryPointInfo(name="serve", entry_type="main_function", file="app.py", description="")
            ],
            tech_stack={"python": {"testing": ["pytest"]}},
            metrics=CodeMetrics(
                total_files=5,
                files_by_layer={"api": 5},
                lines_by_layer={"api": 250},
                total_lines=250,
            ),
            layer_interactions="Simple single-layer architecture.",
        )

        json_str = original.to_json()
        restored = SynthesisMap.from_json(json_str)

        assert len(restored.entry_points) == 1
        assert restored.entry_points[0].name == "serve"
        assert restored.tech_stack["python"]["testing"] == ["pytest"]
        assert restored.metrics.total_files == 5
        assert restored.layer_interactions == "Simple single-layer architecture."
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestSynthesisMapExtended -v`

Expected: FAIL with TypeError about unexpected keyword argument

**Step 3: Write minimal implementation**

Modify `SynthesisMap` class in `backend/src/oya/generation/summaries.py`:

```python
@dataclass
class SynthesisMap:
    """Aggregated codebase understanding synthesized from file and directory summaries.

    Combines all File_Summaries and Directory_Summaries into a coherent map of the
    codebase, including layer groupings, key components, and dependency relationships.
    This serves as the primary context for generating Architecture and Overview pages.

    Attributes:
        layers: Mapping of layer names to LayerInfo objects.
        key_components: List of important components identified across the codebase.
        dependency_graph: Mapping of component/layer names to their dependencies.
        project_summary: LLM-generated overall summary of the project.
        entry_points: Discovered CLI commands, API routes, main functions.
        tech_stack: Categorized libraries by language and category.
        metrics: Code statistics (file counts, LOC by layer).
        layer_interactions: LLM-generated description of how layers communicate.
    """

    layers: dict[str, LayerInfo] = field(default_factory=dict)
    key_components: list[ComponentInfo] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    project_summary: str = ""
    entry_points: list[EntryPointInfo] = field(default_factory=list)
    tech_stack: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    metrics: CodeMetrics | None = None
    layer_interactions: str = ""

    def to_json(self) -> str:
        """Serialize the SynthesisMap to a JSON string."""
        data = {
            "layers": {
                name: {
                    "name": layer.name,
                    "purpose": layer.purpose,
                    "directories": layer.directories,
                    "files": layer.files,
                }
                for name, layer in self.layers.items()
            },
            "key_components": [
                {
                    "name": comp.name,
                    "file": comp.file,
                    "role": comp.role,
                    "layer": comp.layer,
                }
                for comp in self.key_components
            ],
            "dependency_graph": self.dependency_graph,
            "project_summary": self.project_summary,
            "entry_points": [ep.to_dict() for ep in self.entry_points],
            "tech_stack": self.tech_stack,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "layer_interactions": self.layer_interactions,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "SynthesisMap":
        """Deserialize a SynthesisMap from a JSON string."""
        data = json.loads(json_str)

        layers = {
            name: LayerInfo(
                name=layer_data["name"],
                purpose=layer_data["purpose"],
                directories=layer_data.get("directories", []),
                files=layer_data.get("files", []),
            )
            for name, layer_data in data.get("layers", {}).items()
        }

        key_components = [
            ComponentInfo(
                name=comp["name"],
                file=comp["file"],
                role=comp["role"],
                layer=comp["layer"],
            )
            for comp in data.get("key_components", [])
        ]

        entry_points = [
            EntryPointInfo.from_dict(ep) for ep in data.get("entry_points", [])
        ]

        metrics_data = data.get("metrics")
        metrics = CodeMetrics.from_dict(metrics_data) if metrics_data else None

        return cls(
            layers=layers,
            key_components=key_components,
            dependency_graph=data.get("dependency_graph", {}),
            project_summary=data.get("project_summary", ""),
            entry_points=entry_points,
            tech_stack=data.get("tech_stack", {}),
            metrics=metrics,
            layer_interactions=data.get("layer_interactions", ""),
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_summaries.py::TestSynthesisMapExtended -v`

Expected: PASS (2 tests)

**Step 5: Run all summaries tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_summaries.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/src/oya/generation/summaries.py backend/tests/test_summaries.py
git commit -m "feat: extend SynthesisMap with entry_points, tech_stack, metrics, layer_interactions"
```

---

## Task 4: Create Tech Stack Config File

**Files:**
- Create: `backend/src/oya/constants/techstack.yaml`
- Test: (manual verification)

**Step 1: Create the config file**

Create `backend/src/oya/constants/techstack.yaml`:

```yaml
# Technology stack library mappings
# Maps library/package names to language, category, and display name
#
# Categories: web_framework, database, testing, cli, object_system,
#             http_client, async, validation, serialization, logging,
#             auth, caching, messaging, templating

libraries:
  # =============================================================================
  # Python
  # =============================================================================
  fastapi:
    language: python
    category: web_framework
    display: FastAPI
  flask:
    language: python
    category: web_framework
    display: Flask
  django:
    language: python
    category: web_framework
    display: Django
  starlette:
    language: python
    category: web_framework
    display: Starlette
  tornado:
    language: python
    category: web_framework
    display: Tornado
  bottle:
    language: python
    category: web_framework
    display: Bottle
  aiohttp:
    language: python
    category: web_framework
    display: aiohttp

  sqlalchemy:
    language: python
    category: database
    display: SQLAlchemy
  peewee:
    language: python
    category: database
    display: Peewee
  tortoise-orm:
    language: python
    category: database
    display: Tortoise ORM
  pymongo:
    language: python
    category: database
    display: PyMongo
  redis:
    language: python
    category: database
    display: Redis
  psycopg2:
    language: python
    category: database
    display: psycopg2

  pytest:
    language: python
    category: testing
    display: pytest
  unittest:
    language: python
    category: testing
    display: unittest
  hypothesis:
    language: python
    category: testing
    display: Hypothesis

  click:
    language: python
    category: cli
    display: Click
  typer:
    language: python
    category: cli
    display: Typer
  argparse:
    language: python
    category: cli
    display: argparse

  pydantic:
    language: python
    category: validation
    display: Pydantic
  marshmallow:
    language: python
    category: validation
    display: Marshmallow
  attrs:
    language: python
    category: validation
    display: attrs

  requests:
    language: python
    category: http_client
    display: Requests
  httpx:
    language: python
    category: http_client
    display: HTTPX
  aiohttp:
    language: python
    category: http_client
    display: aiohttp

  celery:
    language: python
    category: messaging
    display: Celery
  rq:
    language: python
    category: messaging
    display: RQ

  jinja2:
    language: python
    category: templating
    display: Jinja2

  # =============================================================================
  # JavaScript / TypeScript
  # =============================================================================
  express:
    language: javascript
    category: web_framework
    display: Express
  fastify:
    language: javascript
    category: web_framework
    display: Fastify
  koa:
    language: javascript
    category: web_framework
    display: Koa
  hapi:
    language: javascript
    category: web_framework
    display: Hapi
  nest:
    language: javascript
    category: web_framework
    display: NestJS
  next:
    language: javascript
    category: web_framework
    display: Next.js
  nuxt:
    language: javascript
    category: web_framework
    display: Nuxt

  react:
    language: javascript
    category: frontend
    display: React
  vue:
    language: javascript
    category: frontend
    display: Vue.js
  angular:
    language: javascript
    category: frontend
    display: Angular
  svelte:
    language: javascript
    category: frontend
    display: Svelte

  prisma:
    language: javascript
    category: database
    display: Prisma
  typeorm:
    language: javascript
    category: database
    display: TypeORM
  sequelize:
    language: javascript
    category: database
    display: Sequelize
  mongoose:
    language: javascript
    category: database
    display: Mongoose
  knex:
    language: javascript
    category: database
    display: Knex.js

  jest:
    language: javascript
    category: testing
    display: Jest
  vitest:
    language: javascript
    category: testing
    display: Vitest
  mocha:
    language: javascript
    category: testing
    display: Mocha
  cypress:
    language: javascript
    category: testing
    display: Cypress
  playwright:
    language: javascript
    category: testing
    display: Playwright

  commander:
    language: javascript
    category: cli
    display: Commander.js
  yargs:
    language: javascript
    category: cli
    display: Yargs

  zod:
    language: javascript
    category: validation
    display: Zod
  joi:
    language: javascript
    category: validation
    display: Joi
  yup:
    language: javascript
    category: validation
    display: Yup

  axios:
    language: javascript
    category: http_client
    display: Axios

  # =============================================================================
  # Perl
  # =============================================================================
  mojolicious:
    language: perl
    category: web_framework
    display: Mojolicious
  dancer:
    language: perl
    category: web_framework
    display: Dancer
  dancer2:
    language: perl
    category: web_framework
    display: Dancer2
  catalyst:
    language: perl
    category: web_framework
    display: Catalyst
  plack:
    language: perl
    category: web_framework
    display: Plack
  cgi:
    language: perl
    category: web_framework
    display: CGI

  dbi:
    language: perl
    category: database
    display: DBI
  dbix-class:
    language: perl
    category: database
    display: DBIx::Class
  rose-db:
    language: perl
    category: database
    display: Rose::DB
  dbix-connector:
    language: perl
    category: database
    display: DBIx::Connector

  test-more:
    language: perl
    category: testing
    display: Test::More
  test-simple:
    language: perl
    category: testing
    display: Test::Simple
  test2:
    language: perl
    category: testing
    display: Test2
  test-class:
    language: perl
    category: testing
    display: Test::Class
  test-deep:
    language: perl
    category: testing
    display: Test::Deep

  moose:
    language: perl
    category: object_system
    display: Moose
  moo:
    language: perl
    category: object_system
    display: Moo
  mouse:
    language: perl
    category: object_system
    display: Mouse
  moosex-extended:
    language: perl
    category: object_system
    display: MooseX::Extended

  lwp:
    language: perl
    category: http_client
    display: LWP
  http-tiny:
    language: perl
    category: http_client
    display: HTTP::Tiny
  mojo-useragent:
    language: perl
    category: http_client
    display: Mojo::UserAgent

  template-toolkit:
    language: perl
    category: templating
    display: Template Toolkit
  text-xslate:
    language: perl
    category: templating
    display: Text::Xslate

  json:
    language: perl
    category: serialization
    display: JSON
  cpanel-json-xs:
    language: perl
    category: serialization
    display: Cpanel::JSON::XS

  # =============================================================================
  # Go
  # =============================================================================
  gin:
    language: go
    category: web_framework
    display: Gin
  echo:
    language: go
    category: web_framework
    display: Echo
  fiber:
    language: go
    category: web_framework
    display: Fiber
  chi:
    language: go
    category: web_framework
    display: Chi
  gorilla:
    language: go
    category: web_framework
    display: Gorilla Mux

  gorm:
    language: go
    category: database
    display: GORM
  sqlx:
    language: go
    category: database
    display: sqlx
  ent:
    language: go
    category: database
    display: Ent

  testify:
    language: go
    category: testing
    display: Testify
  gomega:
    language: go
    category: testing
    display: Gomega
  ginkgo:
    language: go
    category: testing
    display: Ginkgo

  cobra:
    language: go
    category: cli
    display: Cobra
  urfave-cli:
    language: go
    category: cli
    display: urfave/cli

  # =============================================================================
  # Rust
  # =============================================================================
  actix-web:
    language: rust
    category: web_framework
    display: Actix Web
  axum:
    language: rust
    category: web_framework
    display: Axum
  rocket:
    language: rust
    category: web_framework
    display: Rocket
  warp:
    language: rust
    category: web_framework
    display: Warp

  diesel:
    language: rust
    category: database
    display: Diesel
  sqlx:
    language: rust
    category: database
    display: SQLx
  sea-orm:
    language: rust
    category: database
    display: SeaORM

  tokio:
    language: rust
    category: async
    display: Tokio

  serde:
    language: rust
    category: serialization
    display: Serde

  clap:
    language: rust
    category: cli
    display: Clap

  # =============================================================================
  # Java
  # =============================================================================
  spring:
    language: java
    category: web_framework
    display: Spring
  spring-boot:
    language: java
    category: web_framework
    display: Spring Boot
  quarkus:
    language: java
    category: web_framework
    display: Quarkus
  micronaut:
    language: java
    category: web_framework
    display: Micronaut

  hibernate:
    language: java
    category: database
    display: Hibernate
  jpa:
    language: java
    category: database
    display: JPA
  mybatis:
    language: java
    category: database
    display: MyBatis

  junit:
    language: java
    category: testing
    display: JUnit
  testng:
    language: java
    category: testing
    display: TestNG
  mockito:
    language: java
    category: testing
    display: Mockito

  # =============================================================================
  # Ruby
  # =============================================================================
  rails:
    language: ruby
    category: web_framework
    display: Ruby on Rails
  sinatra:
    language: ruby
    category: web_framework
    display: Sinatra
  hanami:
    language: ruby
    category: web_framework
    display: Hanami

  activerecord:
    language: ruby
    category: database
    display: ActiveRecord
  sequel:
    language: ruby
    category: database
    display: Sequel

  rspec:
    language: ruby
    category: testing
    display: RSpec
  minitest:
    language: ruby
    category: testing
    display: Minitest
```

**Step 2: Verify file created**

Run: `ls -la backend/src/oya/constants/techstack.yaml`

Expected: File exists

**Step 3: Commit**

```bash
git add backend/src/oya/constants/techstack.yaml
git commit -m "feat: add tech stack library mappings config file"
```

---

## Task 5: Create Tech Stack Detection Module

**Files:**
- Create: `backend/src/oya/generation/techstack.py`
- Create: `backend/tests/test_techstack.py`

**Step 1: Write the failing test**

Create `backend/tests/test_techstack.py`:

```python
"""Tests for tech stack detection."""

import pytest

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
        # Unknown libs should not cause errors or appear

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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_techstack.py -v`

Expected: FAIL with "No module named 'oya.generation.techstack'"

**Step 3: Write minimal implementation**

Create `backend/src/oya/generation/techstack.py`:

```python
"""Tech stack detection from file summaries.

Aggregates external dependencies from FileSummaries and maps them to
known libraries using the techstack.yaml configuration.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from oya.generation.summaries import FileSummary


@lru_cache(maxsize=1)
def load_techstack_config() -> dict[str, Any]:
    """Load tech stack configuration from YAML file.

    Returns:
        Dictionary containing library mappings.
    """
    config_path = Path(__file__).parent.parent / "constants" / "techstack.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def detect_tech_stack(
    file_summaries: list[FileSummary],
) -> dict[str, dict[str, list[str]]]:
    """Detect technology stack from file summaries.

    Aggregates external_deps from all file summaries and maps known
    libraries to their language and category.

    Args:
        file_summaries: List of FileSummary objects with external_deps.

    Returns:
        Nested dict: {language: {category: [display_names]}}
        Example: {"python": {"web_framework": ["FastAPI"]}}
    """
    config = load_techstack_config()
    libraries = config.get("libraries", {})

    # Collect all external deps
    all_deps: set[str] = set()
    for summary in file_summaries:
        all_deps.update(summary.external_deps)

    # Map to known libraries
    result: dict[str, dict[str, list[str]]] = {}

    for dep in all_deps:
        # Normalize dependency name (lowercase, handle common variations)
        dep_normalized = dep.lower().replace("_", "-").replace("::", "-")

        if dep_normalized in libraries:
            lib_info = libraries[dep_normalized]
            language = lib_info["language"]
            category = lib_info["category"]
            display = lib_info["display"]

            if language not in result:
                result[language] = {}
            if category not in result[language]:
                result[language][category] = []
            if display not in result[language][category]:
                result[language][category].append(display)

    return result
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_techstack.py -v`

Expected: PASS (9 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/techstack.py backend/tests/test_techstack.py
git commit -m "feat: add tech stack detection module"
```

---

## Task 6: Create Code Metrics Module

**Files:**
- Create: `backend/src/oya/generation/metrics.py`
- Create: `backend/tests/test_metrics.py`

**Step 1: Write the failing test**

Create `backend/tests/test_metrics.py`:

```python
"""Tests for code metrics computation."""

import pytest

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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_metrics.py -v`

Expected: FAIL with "No module named 'oya.generation.metrics'"

**Step 3: Write minimal implementation**

Create `backend/src/oya/generation/metrics.py`:

```python
"""Code metrics computation from file summaries.

Computes quantitative metrics about codebase size and distribution
across architectural layers.
"""

from __future__ import annotations

from collections import defaultdict

from oya.generation.summaries import CodeMetrics, FileSummary


def compute_code_metrics(
    file_summaries: list[FileSummary],
    file_contents: dict[str, str],
) -> CodeMetrics:
    """Compute code metrics from analyzed files.

    Args:
        file_summaries: List of FileSummary objects with layer classifications.
        file_contents: Mapping of file paths to their contents for LOC counting.

    Returns:
        CodeMetrics with file counts and lines of code by layer.
    """
    files_by_layer: dict[str, int] = defaultdict(int)
    lines_by_layer: dict[str, int] = defaultdict(int)

    for summary in file_summaries:
        layer = summary.layer
        files_by_layer[layer] += 1

        content = file_contents.get(summary.file_path, "")
        if content:
            loc = len(content.splitlines())
            lines_by_layer[layer] += loc

    return CodeMetrics(
        total_files=len(file_summaries),
        files_by_layer=dict(files_by_layer),
        lines_by_layer=dict(lines_by_layer),
        total_lines=sum(lines_by_layer.values()),
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_metrics.py -v`

Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/metrics.py backend/tests/test_metrics.py
git commit -m "feat: add code metrics computation module"
```

---

## Task 7: Add Entry Point Extraction Helper

**Files:**
- Modify: `backend/src/oya/generation/workflows.py`
- Test: `backend/tests/test_workflow_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_workflow_generator.py`:

```python
class TestExtractEntryPointDescription:
    """Tests for entry point description extraction."""

    def test_extracts_route_path_from_decorator(self):
        """Test extraction of route path from route decorator."""
        from oya.generation.workflows import extract_entry_point_description
        from oya.parsing.models import ParsedSymbol, SymbolType

        symbol = ParsedSymbol(
            name="get_users",
            symbol_type=SymbolType.ROUTE,
            line=10,
            decorators=["@router.get('/users')"],
            metadata={"file": "api/users.py"},
        )

        result = extract_entry_point_description(symbol)

        assert result == "/users"

    def test_extracts_cli_command_from_decorator(self):
        """Test extraction of CLI command name from decorator."""
        from oya.generation.workflows import extract_entry_point_description
        from oya.parsing.models import ParsedSymbol, SymbolType

        symbol = ParsedSymbol(
            name="init_cmd",
            symbol_type=SymbolType.CLI_COMMAND,
            line=10,
            decorators=["@click.command('init')"],
            metadata={"file": "cli/commands.py"},
        )

        result = extract_entry_point_description(symbol)

        assert result == "init"

    def test_returns_empty_for_main_function(self):
        """Test that main functions return empty description."""
        from oya.generation.workflows import extract_entry_point_description
        from oya.parsing.models import ParsedSymbol, SymbolType

        symbol = ParsedSymbol(
            name="main",
            symbol_type=SymbolType.FUNCTION,
            line=10,
            decorators=[],
            metadata={"file": "main.py"},
        )

        result = extract_entry_point_description(symbol)

        assert result == ""

    def test_handles_complex_route_decorator(self):
        """Test extraction from complex route decorators."""
        from oya.generation.workflows import extract_entry_point_description
        from oya.parsing.models import ParsedSymbol, SymbolType

        symbol = ParsedSymbol(
            name="create_user",
            symbol_type=SymbolType.ROUTE,
            line=10,
            decorators=["@app.post('/api/v1/users', status_code=201)"],
            metadata={"file": "api/users.py"},
        )

        result = extract_entry_point_description(symbol)

        assert result == "/api/v1/users"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestExtractEntryPointDescription -v`

Expected: FAIL with "cannot import name 'extract_entry_point_description'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/workflows.py`:

```python
import re


def extract_entry_point_description(symbol: ParsedSymbol) -> str:
    """Extract description from an entry point symbol.

    For routes: extracts the path (e.g., "/users" from "@app.get('/users')").
    For CLI commands: extracts the command name.
    For main functions: returns empty string.

    Args:
        symbol: ParsedSymbol representing an entry point.

    Returns:
        Description string (route path, CLI command, or empty).
    """
    # Check decorators for route paths or CLI commands
    for decorator in symbol.decorators:
        # Route pattern: @app.get('/path') or @router.post("/path")
        route_match = re.search(r"\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]", decorator)
        if route_match:
            return route_match.group(2)

        # CLI command pattern: @click.command('name') or @typer.command("name")
        cli_match = re.search(r"\.command\(['\"]([^'\"]+)['\"]", decorator)
        if cli_match:
            return cli_match.group(1)

    return ""
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_workflow_generator.py::TestExtractEntryPointDescription -v`

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/workflows.py backend/tests/test_workflow_generator.py
git commit -m "feat: add entry point description extraction helper"
```

---

## Task 8: Update Synthesis Prompt for layer_interactions

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py` (create if doesn't exist):

```python
"""Tests for prompt templates."""

import pytest


class TestSynthesisTemplate:
    """Tests for synthesis prompt template."""

    def test_synthesis_template_requests_layer_interactions(self):
        """Test that synthesis template asks for layer_interactions field."""
        from oya.generation.prompts import SYNTHESIS_TEMPLATE

        template_str = SYNTHESIS_TEMPLATE.template

        assert "layer_interactions" in template_str
        assert "how the architectural layers communicate" in template_str.lower() or \
               "how layers communicate" in template_str.lower()

    def test_synthesis_template_json_schema_includes_layer_interactions(self):
        """Test that JSON schema in synthesis template includes layer_interactions."""
        from oya.generation.prompts import SYNTHESIS_TEMPLATE

        template_str = SYNTHESIS_TEMPLATE.template

        # Should have layer_interactions in the JSON example
        assert '"layer_interactions"' in template_str
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestSynthesisTemplate -v`

Expected: FAIL (assertions fail - layer_interactions not in template)

**Step 3: Update the implementation**

Modify `SYNTHESIS_TEMPLATE` in `backend/src/oya/generation/prompts.py`:

```python
SYNTHESIS_TEMPLATE = PromptTemplate(
    """Synthesize the following file and directory summaries into a coherent understanding of the codebase.

## File Summaries
{file_summaries}

## Directory Summaries
{directory_summaries}

---

Analyze the summaries above and produce a JSON response with the following structure:

```json
{{
  "key_components": [
    {{
      "name": "ComponentName",
      "file": "path/to/file.py",
      "role": "Description of what this component does and why it's important",
      "layer": "api|domain|infrastructure|utility|config|test"
    }}
  ],
  "dependency_graph": {{
    "layer_name": ["dependent_layer1", "dependent_layer2"]
  }},
  "project_summary": "A comprehensive 2-3 sentence summary of what this project does, its main purpose, and key technologies used.",
  "layer_interactions": "A 2-4 sentence description of how the architectural layers communicate with each other. Describe the flow of data and control between layers, including patterns used (direct calls, dependency injection, events, etc.)."
}}
```

Guidelines:
1. **key_components**: Identify the 5-15 most important classes, functions, or modules that form the backbone of the system. Focus on:
   - Entry points and main orchestrators
   - Core domain models and services
   - Key infrastructure components
   - Important utilities used throughout

2. **dependency_graph**: Map which layers depend on which other layers. For example, "api" typically depends on "domain", and "domain" may depend on "infrastructure".

3. **project_summary**: Write a clear, informative summary that would help a new developer understand what this codebase does at a glance.

4. **layer_interactions**: Describe how code flows between layers. Focus on the patterns used for communication and the direction of dependencies. Be concrete but concise. For example: "API handlers delegate to domain services via dependency injection. Domain services access data through repository interfaces implemented in the infrastructure layer."

Respond with valid JSON only, no additional text."""
)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestSynthesisTemplate -v`

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: add layer_interactions to synthesis prompt template"
```

---

## Task 9: Add Prompt Helper Functions for New Fields

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py`:

```python
class TestFormatHelpers:
    """Tests for prompt formatting helper functions."""

    def test_format_entry_points(self):
        """Test formatting entry points for prompt."""
        from oya.generation.prompts import _format_entry_points
        from oya.generation.summaries import EntryPointInfo

        entry_points = [
            EntryPointInfo(name="main", entry_type="main_function", file="main.py", description=""),
            EntryPointInfo(name="get_users", entry_type="api_route", file="api/users.py", description="/users"),
            EntryPointInfo(name="init", entry_type="cli_command", file="cli/main.py", description="init"),
        ]

        result = _format_entry_points(entry_points)

        assert "main" in result
        assert "main_function" in result
        assert "main.py" in result
        assert "/users" in result
        assert "cli_command" in result

    def test_format_entry_points_empty(self):
        """Test formatting empty entry points list."""
        from oya.generation.prompts import _format_entry_points

        result = _format_entry_points([])

        assert "No entry points" in result or result == ""

    def test_format_tech_stack(self):
        """Test formatting tech stack for prompt."""
        from oya.generation.prompts import _format_tech_stack

        tech_stack = {
            "python": {
                "web_framework": ["FastAPI"],
                "database": ["SQLAlchemy"],
            },
            "javascript": {
                "frontend": ["React"],
            },
        }

        result = _format_tech_stack(tech_stack)

        assert "Python" in result or "python" in result
        assert "FastAPI" in result
        assert "SQLAlchemy" in result
        assert "React" in result

    def test_format_tech_stack_empty(self):
        """Test formatting empty tech stack."""
        from oya.generation.prompts import _format_tech_stack

        result = _format_tech_stack({})

        assert "No technology" in result.lower() or result == ""

    def test_format_metrics(self):
        """Test formatting code metrics for prompt."""
        from oya.generation.prompts import _format_metrics
        from oya.generation.summaries import CodeMetrics

        metrics = CodeMetrics(
            total_files=50,
            files_by_layer={"api": 10, "domain": 20, "test": 20},
            lines_by_layer={"api": 1000, "domain": 3000, "test": 2000},
            total_lines=6000,
        )

        result = _format_metrics(metrics)

        assert "50" in result  # total files
        assert "6000" in result or "6,000" in result  # total lines
        assert "api" in result.lower()
        assert "domain" in result.lower()

    def test_format_metrics_none(self):
        """Test formatting None metrics."""
        from oya.generation.prompts import _format_metrics

        result = _format_metrics(None)

        assert "No metrics" in result or result == ""
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestFormatHelpers -v`

Expected: FAIL with "cannot import name '_format_entry_points'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/prompts.py`:

```python
def _format_entry_points(entry_points: list[Any]) -> str:
    """Format entry points for inclusion in a prompt.

    Args:
        entry_points: List of EntryPointInfo objects.

    Returns:
        Formatted string representation of entry points.
    """
    if not entry_points:
        return "No entry points discovered."

    lines = []
    for ep in entry_points:
        desc = f" ({ep.description})" if ep.description else ""
        lines.append(f"- **{ep.name}** ({ep.entry_type}) in `{ep.file}`{desc}")

    return "\n".join(lines)


def _format_tech_stack(tech_stack: dict[str, dict[str, list[str]]]) -> str:
    """Format tech stack for inclusion in a prompt.

    Args:
        tech_stack: Nested dict of {language: {category: [libraries]}}.

    Returns:
        Formatted string representation of tech stack.
    """
    if not tech_stack:
        return "No technology stack detected."

    lines = []
    for language, categories in sorted(tech_stack.items()):
        lines.append(f"### {language.title()}")
        for category, libraries in sorted(categories.items()):
            category_display = category.replace("_", " ").title()
            libs = ", ".join(libraries)
            lines.append(f"- **{category_display}**: {libs}")
        lines.append("")

    return "\n".join(lines).strip()


def _format_metrics(metrics: Any) -> str:
    """Format code metrics for inclusion in a prompt.

    Args:
        metrics: CodeMetrics object or None.

    Returns:
        Formatted string representation of metrics.
    """
    if metrics is None:
        return "No metrics available."

    lines = [
        f"- **Total Files**: {metrics.total_files}",
        f"- **Total Lines of Code**: {metrics.total_lines:,}",
        "",
        "**By Layer:**",
    ]

    for layer in sorted(metrics.files_by_layer.keys()):
        files = metrics.files_by_layer.get(layer, 0)
        loc = metrics.lines_by_layer.get(layer, 0)
        lines.append(f"- {layer}: {files} files, {loc:,} lines")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestFormatHelpers -v`

Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: add formatting helpers for entry_points, tech_stack, metrics"
```

---

## Task 10: Update Overview Synthesis Template

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py`:

```python
class TestOverviewSynthesisTemplate:
    """Tests for overview synthesis prompt template."""

    def test_template_includes_new_fields(self):
        """Test that template includes placeholders for new fields."""
        from oya.generation.prompts import OVERVIEW_SYNTHESIS_TEMPLATE

        template_str = OVERVIEW_SYNTHESIS_TEMPLATE.template

        assert "{entry_points}" in template_str
        assert "{tech_stack}" in template_str
        assert "{metrics}" in template_str
        assert "{layer_interactions}" in template_str
        assert "{architecture_diagram}" in template_str

    def test_template_deprioritizes_readme(self):
        """Test that template indicates README may be outdated."""
        from oya.generation.prompts import OVERVIEW_SYNTHESIS_TEMPLATE

        template_str = OVERVIEW_SYNTHESIS_TEMPLATE.template.lower()

        assert "outdated" in template_str or "supplementary" in template_str

    def test_template_has_structured_output(self):
        """Test that template specifies structured output format."""
        from oya.generation.prompts import OVERVIEW_SYNTHESIS_TEMPLATE

        template_str = OVERVIEW_SYNTHESIS_TEMPLATE.template

        # Should have main sections
        assert "## Overview" in template_str or "# {repo_name}" in template_str
        assert "Technology Stack" in template_str
        assert "Getting Started" in template_str
        assert "Architecture" in template_str
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestOverviewSynthesisTemplate -v`

Expected: FAIL (assertions fail - new placeholders not in template)

**Step 3: Update the implementation**

Update `OVERVIEW_SYNTHESIS_TEMPLATE` in `backend/src/oya/generation/prompts.py`:

```python
OVERVIEW_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate a comprehensive overview page for the repository "{repo_name}".

## Project Summary (from code analysis)
{project_summary}

## Entry Points
{entry_points}

## Technology Stack
{tech_stack}

## Code Metrics
{metrics}

## System Layers
{layers}

## Layer Interactions
{layer_interactions}

## Key Components
{key_components}

## Architecture Diagram (pre-generated)
{architecture_diagram}

## README Content (supplementary - may be outdated)
{readme_content}

## Project Structure
```
{file_tree}
```

## Package Information
{package_info}

---

Generate the overview using this EXACT structure:

# {repo_name}

## Overview
[2-3 paragraph summary from code analysis. README may be outdated—only incorporate README content if it adds unique context not already covered by the code analysis.]

## Technology Stack
[Table or bullet list of detected technologies organized by language and category. Use the tech stack information provided above.]

## Getting Started
[Based on discovered entry points—describe how to run the project using the CLI commands, API startup methods, or main functions identified. Be specific about commands and files.]

## Architecture
[Brief description of the layer structure with metrics for scale context. Include the pre-generated architecture diagram below this description.]

{architecture_diagram}

## Key Components
[Bullet list of the most important classes/functions and their roles, based on the key components provided above.]

## Optional sections (include only if relevant and supported by the data provided):
- **Configuration**: If notable config patterns exist in the codebase
- **Testing**: If test structure is worth highlighting (based on metrics)
- **API Reference**: If entry points reveal a clear API surface

Format as clean Markdown. Do not invent information not provided in the context above."""
)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestOverviewSynthesisTemplate -v`

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: update overview synthesis template with new fields and structured output"
```

---

## Task 11: Update get_overview_prompt Function

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_prompts.py`:

```python
class TestGetOverviewPrompt:
    """Tests for get_overview_prompt function."""

    def test_includes_entry_points_in_prompt(self):
        """Test that entry points are included in generated prompt."""
        from oya.generation.prompts import get_overview_prompt
        from oya.generation.summaries import (
            SynthesisMap,
            EntryPointInfo,
            CodeMetrics,
            LayerInfo,
        )

        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP", directories=[], files=[])},
            project_summary="Test project",
            entry_points=[
                EntryPointInfo(name="main", entry_type="main_function", file="main.py", description="")
            ],
            tech_stack={"python": {"web_framework": ["FastAPI"]}},
            metrics=CodeMetrics(
                total_files=10,
                files_by_layer={"api": 10},
                lines_by_layer={"api": 500},
                total_lines=500,
            ),
            layer_interactions="API calls domain directly.",
        )

        result = get_overview_prompt(
            repo_name="test-repo",
            readme_content="Test README",
            file_tree="test/\n  main.py",
            package_info={},
            synthesis_map=synthesis_map,
            architecture_diagram="```mermaid\ngraph TD\n```",
        )

        assert "main" in result
        assert "main_function" in result
        assert "FastAPI" in result
        assert "500" in result
        assert "API calls domain" in result
        assert "mermaid" in result

    def test_works_without_architecture_diagram(self):
        """Test that function works when no diagram is provided."""
        from oya.generation.prompts import get_overview_prompt
        from oya.generation.summaries import SynthesisMap

        synthesis_map = SynthesisMap(project_summary="Test")

        result = get_overview_prompt(
            repo_name="test-repo",
            readme_content="Test",
            file_tree="test/",
            package_info={},
            synthesis_map=synthesis_map,
        )

        assert "test-repo" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestGetOverviewPrompt -v`

Expected: FAIL (function doesn't accept new parameters)

**Step 3: Update the implementation**

Update `get_overview_prompt` in `backend/src/oya/generation/prompts.py`:

```python
def get_overview_prompt(
    repo_name: str,
    readme_content: str,
    file_tree: str,
    package_info: dict[str, Any],
    synthesis_map: Any = None,
    architecture_diagram: str = "",
) -> str:
    """Generate a prompt for creating an overview page.

    Supports two modes:
    1. Legacy mode: Uses README as primary context
    2. Synthesis mode: Uses SynthesisMap as primary context with README as supplementary

    Args:
        repo_name: Name of the repository.
        readme_content: Content of the README file.
        file_tree: String representation of the file tree.
        package_info: Dictionary of package metadata.
        synthesis_map: SynthesisMap object with layer and component info (preferred).
        architecture_diagram: Pre-generated Mermaid diagram (optional).

    Returns:
        The rendered prompt string.
    """
    # Use synthesis-based template if synthesis_map is provided
    if synthesis_map is not None:
        return OVERVIEW_SYNTHESIS_TEMPLATE.render(
            repo_name=repo_name,
            project_summary=synthesis_map.project_summary or "No project summary available.",
            layers=_format_synthesis_layers(synthesis_map),
            key_components=_format_synthesis_key_components(synthesis_map),
            entry_points=_format_entry_points(synthesis_map.entry_points),
            tech_stack=_format_tech_stack(synthesis_map.tech_stack),
            metrics=_format_metrics(synthesis_map.metrics),
            layer_interactions=synthesis_map.layer_interactions or "No layer interaction information available.",
            architecture_diagram=architecture_diagram or "No architecture diagram available.",
            readme_content=readme_content or "No README found.",
            file_tree=file_tree,
            package_info=_format_package_info(package_info),
        )

    # Fall back to legacy template without synthesis_map
    return OVERVIEW_TEMPLATE.render(
        repo_name=repo_name,
        readme_content=readme_content or "No README found.",
        file_tree=file_tree,
        package_info=_format_package_info(package_info),
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py::TestGetOverviewPrompt -v`

Expected: PASS (2 tests)

**Step 5: Run all prompt tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_prompts.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/src/oya/generation/prompts.py backend/tests/test_prompts.py
git commit -m "feat: update get_overview_prompt to use new SynthesisMap fields"
```

---

## Task 12: Update Overview Generator

**Files:**
- Modify: `backend/src/oya/generation/overview.py`
- Test: `backend/tests/test_overview_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_overview_generator.py` (or create):

```python
"""Tests for overview generator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from oya.generation.summaries import (
    SynthesisMap,
    EntryPointInfo,
    CodeMetrics,
    LayerInfo,
)


class TestOverviewGeneratorWithDiagram:
    """Tests for OverviewGenerator with architecture diagram."""

    @pytest.mark.asyncio
    async def test_generate_accepts_architecture_diagram(self):
        """Test that generate method accepts architecture_diagram parameter."""
        from oya.generation.overview import OverviewGenerator

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "# Test Overview\n\nGenerated content."

        mock_repo = MagicMock()
        mock_repo.path.name = "test-repo"

        generator = OverviewGenerator(mock_llm, mock_repo)

        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP", directories=[], files=[])},
            project_summary="Test project",
            entry_points=[
                EntryPointInfo(name="main", entry_type="main_function", file="main.py", description="")
            ],
            tech_stack={"python": {"web_framework": ["FastAPI"]}},
            metrics=CodeMetrics(
                total_files=5,
                files_by_layer={"api": 5},
                lines_by_layer={"api": 250},
                total_lines=250,
            ),
            layer_interactions="Simple architecture.",
        )

        result = await generator.generate(
            readme_content="Test README",
            file_tree="test/\n  main.py",
            package_info={"name": "test"},
            synthesis_map=synthesis_map,
            architecture_diagram="```mermaid\ngraph TD\n  A-->B\n```",
        )

        assert result.content == "# Test Overview\n\nGenerated content."
        assert result.page_type == "overview"

        # Verify the diagram was passed to the prompt
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        assert "mermaid" in prompt
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_overview_generator.py::TestOverviewGeneratorWithDiagram -v`

Expected: FAIL (generate doesn't accept architecture_diagram)

**Step 3: Update the implementation**

Update `OverviewGenerator.generate` in `backend/src/oya/generation/overview.py`:

```python
async def generate(
    self,
    readme_content: str | None,
    file_tree: str,
    package_info: dict[str, Any],
    synthesis_map: SynthesisMap | None = None,
    architecture_diagram: str = "",
) -> GeneratedPage:
    """Generate the overview page.

    Supports two modes:
    1. Legacy mode: Uses README as primary context
    2. Synthesis mode: Uses SynthesisMap as primary context with README as supplementary

    Args:
        readme_content: Content of README file (if any).
        file_tree: String representation of file structure.
        package_info: Package metadata dict.
        synthesis_map: SynthesisMap with layer and component info (preferred).
        architecture_diagram: Pre-generated Mermaid diagram (optional).

    Returns:
        GeneratedPage with overview content.
    """
    repo_name = self.repo.path.name

    prompt = get_overview_prompt(
        repo_name=repo_name,
        readme_content=readme_content or "",
        file_tree=file_tree,
        package_info=package_info,
        synthesis_map=synthesis_map,
        architecture_diagram=architecture_diagram,
    )

    content = await self.llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
    )

    word_count = len(content.split())

    return GeneratedPage(
        content=content,
        page_type="overview",
        path="overview.md",
        word_count=word_count,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_overview_generator.py::TestOverviewGeneratorWithDiagram -v`

Expected: PASS (1 test)

**Step 5: Commit**

```bash
git add backend/src/oya/generation/overview.py backend/tests/test_overview_generator.py
git commit -m "feat: update OverviewGenerator to accept architecture_diagram"
```

---

## Task 13: Integrate New Fields into Orchestrator Synthesis Phase

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`
- Test: (integration test - verify with full test run)

**Step 1: Understand current orchestrator structure**

Read the relevant sections of orchestrator.py to understand where synthesis happens and how to integrate the new modules.

**Step 2: Update orchestrator imports**

Add to imports in `backend/src/oya/generation/orchestrator.py`:

```python
from oya.generation.metrics import compute_code_metrics
from oya.generation.techstack import detect_tech_stack
from oya.generation.workflows import WorkflowDiscovery, extract_entry_point_description
from oya.generation.summaries import EntryPointInfo
```

**Step 3: Update synthesis phase**

Find the method that creates/updates SynthesisMap (likely `_run_synthesis` or similar) and add:

```python
# After existing synthesis logic that creates synthesis_map:

# Compute tech stack from file summaries
synthesis_map.tech_stack = detect_tech_stack(file_summaries)

# Compute code metrics
synthesis_map.metrics = compute_code_metrics(file_summaries, file_contents)

# Discover entry points
discovery = WorkflowDiscovery()
entry_point_symbols = discovery.find_entry_points(all_symbols)
synthesis_map.entry_points = [
    EntryPointInfo(
        name=ep.name,
        entry_type=ep.symbol_type.value,
        file=ep.metadata.get("file", ""),
        description=extract_entry_point_description(ep),
    )
    for ep in entry_point_symbols
]

# layer_interactions comes from LLM response parsing (already in synthesis)
```

**Step 4: Update overview generation call**

Find `_run_overview` and update to pass architecture diagram:

```python
async def _run_overview(
    self,
    analysis: dict,
    synthesis_map: SynthesisMap | None = None,
) -> GeneratedPage:
    # ... existing code ...

    # Generate architecture diagram if we have synthesis data
    architecture_diagram = ""
    if synthesis_map:
        architecture_diagram = self._generate_architecture_diagram(synthesis_map)

    return await self.overview_generator.generate(
        readme_content=readme_content,
        file_tree=analysis["file_tree"],
        package_info=package_info,
        synthesis_map=synthesis_map,
        architecture_diagram=architecture_diagram,
    )
```

**Step 5: Run full test suite**

Run: `cd backend && source .venv/bin/activate && pytest -x -q`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/src/oya/generation/orchestrator.py
git commit -m "feat: integrate tech_stack, metrics, entry_points into synthesis phase"
```

---

## Task 14: Update Synthesis Response Parsing for layer_interactions

**Files:**
- Modify: `backend/src/oya/generation/synthesis.py` (or wherever synthesis JSON is parsed)
- Test: Verify with existing synthesis tests

**Step 1: Find synthesis parsing code**

Locate where the LLM's JSON response is parsed into SynthesisMap.

**Step 2: Update parsing to extract layer_interactions**

Ensure the JSON parsing extracts `layer_interactions`:

```python
# In the parsing logic:
synthesis_map.layer_interactions = data.get("layer_interactions", "")
```

**Step 3: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_synthesis*.py -v`

Expected: PASS

**Step 4: Commit**

```bash
git add backend/src/oya/generation/synthesis.py
git commit -m "feat: parse layer_interactions from synthesis LLM response"
```

---

## Task 15: Final Integration Test

**Files:**
- All modified files

**Step 1: Run full test suite**

Run: `cd backend && source .venv/bin/activate && pytest -v`

Expected: All tests PASS

**Step 2: Run linting**

Run: `cd backend && source .venv/bin/activate && ruff check src/ tests/`

Expected: No errors (fix any that appear)

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: address linting issues"
```

**Step 4: Final commit and summary**

```bash
git log --oneline -15
```

Review commits and ensure all changes are captured.

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add EntryPointInfo dataclass | summaries.py |
| 2 | Add CodeMetrics dataclass | summaries.py |
| 3 | Extend SynthesisMap with new fields | summaries.py |
| 4 | Create tech stack config file | techstack.yaml |
| 5 | Create tech stack detection module | techstack.py |
| 6 | Create code metrics module | metrics.py |
| 7 | Add entry point description extraction | workflows.py |
| 8 | Update synthesis prompt for layer_interactions | prompts.py |
| 9 | Add formatting helpers for new fields | prompts.py |
| 10 | Update overview synthesis template | prompts.py |
| 11 | Update get_overview_prompt function | prompts.py |
| 12 | Update OverviewGenerator | overview.py |
| 13 | Integrate into orchestrator synthesis | orchestrator.py |
| 14 | Update synthesis response parsing | synthesis.py |
| 15 | Final integration test | all files |
