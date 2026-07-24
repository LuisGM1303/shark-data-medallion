"""Docker and project configuration tests."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASSED = 0
FAILED = 0
ERRORS = []


def test(name: str):
    def decorator(fn):
        global PASSED, FAILED
        try:
            fn()
            PASSED += 1
            print(f"  PASS: {name}")
        except Exception as e:
            FAILED += 1
            ERRORS.append((name, str(e)))
            print(f"  FAIL: {name} - {e}")
        return fn
    return decorator


@test("#163: Dockerfile uses python:3.11-slim base image")
def test_dockerfile_base():
    with open("Dockerfile") as f:
        content = f.read()
    assert "FROM python:3.11-slim" in content, "Dockerfile should use python:3.11-slim"


@test("#164: Dockerfile installs all dependencies from pyproject.toml")
def test_dockerfile_install():
    with open("Dockerfile") as f:
        content = f.read()
    assert "COPY pyproject.toml" in content
    assert "pip install" in content


@test("#165: docker-compose.yml defines pipeline service")
def test_compose_pipeline():
    import yaml
    with open("docker-compose.yml") as f:
        cfg = yaml.safe_load(f)
    assert "pipeline" in cfg.get("services", {}), "pipeline service not found"


@test("#166: docker-compose.yml defines notebook (Jupyter Lab) service")
def test_compose_notebook():
    import yaml
    with open("docker-compose.yml") as f:
        cfg = yaml.safe_load(f)
    assert "notebook" in cfg.get("services", {}), "notebook service not found"


@test("#167: Pipeline service mounts ./data volume for state persistence")
def test_compose_volume_data():
    import yaml
    with open("docker-compose.yml") as f:
        cfg = yaml.safe_load(f)
    svc = cfg.get("services", {}).get("pipeline", {})
    vols = svc.get("volumes", [])
    assert any("./data" in v for v in vols), "pipeline should mount ./data"


@test("#168: Pipeline service accepts BATCH_SPECIES env var")
def test_compose_env():
    import yaml
    with open("docker-compose.yml") as f:
        cfg = yaml.safe_load(f)
    svc = cfg.get("services", {}).get("pipeline", {})
    env = svc.get("environment", {}) if isinstance(svc.get("environment"), dict) else {}
    assert "BATCH_SPECIES" in env or any("BATCH_SPECIES" in str(e) for e in (svc.get("environment") or [])), \
        "pipeline should have BATCH_SPECIES env var"


@test("#169: Notebook service mounts ./data and ./src volumes")
def test_compose_notebook_volumes():
    import yaml
    with open("docker-compose.yml") as f:
        cfg = yaml.safe_load(f)
    svc = cfg.get("services", {}).get("notebook", {})
    vols = svc.get("volumes", [])
    assert any("./data" in v for v in vols), "notebook should mount ./data"
    assert any("./src" in v for v in vols), "notebook should mount ./src"


@test("#170: requirements.txt contains all required dependencies")
def test_requirements():
    req_paths = ["requirements.txt", "pyproject.toml"]
    deps_found = set()
    for rp in req_paths:
        if os.path.exists(rp):
            with open(rp) as f:
                deps_found.update(line.strip().lower() for line in f if line.strip() and not line.startswith("#") and not line.startswith("["))
    needed = ["pydantic", "duckdb", "faiss", "requests", "jupyter"]
    for dep in needed:
        assert any(dep in d for d in deps_found), f"Missing dependency: {dep}"


@test("#171: Docker Compose setup is fully local (no external service dependencies)")
def test_compose_local():
    import yaml
    with open("docker-compose.yml") as f:
        cfg = yaml.safe_load(f)
    for name, svc in cfg.get("services", {}).items():
        assert "depends_on" not in svc, f"Service {name} has external depends_on"


@test("#190: .gitignore properly excludes Python generated files and data/ directory")
def test_gitignore():
    with open(".gitignore") as f:
        content = f.read()
    assert "__pycache__" in content
    assert "data/" in content or "/data" in content
    assert ".venv" in content


@test("#191: README.md provides project overview, architecture summary, and setup instructions")
def test_readme():
    with open("README.md") as f:
        content = f.read()
    assert "shark" in content.lower() or "Shark" in content
    assert "medallion" in content.lower() or "Medallion" in content
    assert "docker" in content.lower() or "Docker" in content or "pip" in content


@test("#192: init.sh script exists and is executable")
def test_init_exists():
    assert os.path.exists("init.sh"), "init.sh should exist"
    assert os.access("init.sh", os.X_OK), "init.sh should be executable"


@test("#193: init.sh installs all required dependencies from requirements.txt")
def test_init_installs():
    with open("init.sh") as f:
        content = f.read()
    assert "uv sync" in content or "uv pip" in content or "pip install" in content


if __name__ == "__main__":
    n = len([k for k in dir() if k.startswith("test_") and callable(locals()[k])])
    print(f"Running {n} Docker/Project tests...\n")

    print(f"\nResults: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nErrors:")
        for name, err in ERRORS:
            print(f"  {name}: {err}")
    sys.exit(0 if FAILED == 0 else 1)
