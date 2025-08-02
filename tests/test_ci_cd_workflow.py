"""Tests for CI/CD workflow validation."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

# Get the project root directory
PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ci_cd_workflow_valid_yaml() -> None:
    """Test that the CI/CD workflow is valid YAML."""
    workflow_path = PROJECT_ROOT / ".github/workflows/ci-cd.yml"
    assert workflow_path.exists(), "CI/CD workflow file does not exist"

    with open(workflow_path) as f:
        workflow_content = f.read()

    # This will raise an exception if YAML is invalid
    workflow_data = yaml.safe_load(workflow_content)

    assert workflow_data is not None, "Workflow file is empty"
    assert "name" in workflow_data, "Workflow must have a name"
    # YAML interprets 'on' as boolean True, so check for True or 'on'
    assert "on" in workflow_data or True in workflow_data, "Workflow must have triggers"
    assert "jobs" in workflow_data, "Workflow must have jobs"


def test_ci_cd_workflow_required_jobs() -> None:
    """Test that all required jobs are present in the workflow."""
    workflow_path = PROJECT_ROOT / ".github/workflows/ci-cd.yml"

    with open(workflow_path) as f:
        workflow_data = yaml.safe_load(f.read())

    jobs = workflow_data.get("jobs", {})

    # Check required jobs exist
    assert "test" in jobs, "Test job is required"
    assert "build" in jobs, "Build job is required"
    assert "deploy-staging" in jobs, "Deploy staging job is required"


def test_ci_cd_workflow_triggers() -> None:
    """Test that workflow has correct triggers configured."""
    workflow_path = PROJECT_ROOT / ".github/workflows/ci-cd.yml"

    with open(workflow_path) as f:
        workflow_data = yaml.safe_load(f.read())

    # YAML interprets 'on' as boolean True
    triggers = workflow_data.get("on", workflow_data.get(True, {}))

    # Check push trigger for main branch
    assert "push" in triggers, "Push trigger is required"
    assert "branches" in triggers["push"], "Push must specify branches"
    assert "main" in triggers["push"]["branches"], "Push must trigger on main branch"

    # Check PR trigger
    assert "pull_request" in triggers, "PR trigger is required"
    assert "branches" in triggers["pull_request"], "PR must specify branches"
    assert "main" in triggers["pull_request"]["branches"], (
        "PR must trigger for main branch"
    )


def test_ci_cd_workflow_environment_variables() -> None:
    """Test that required environment variables are configured."""
    workflow_path = PROJECT_ROOT / ".github/workflows/ci-cd.yml"

    with open(workflow_path) as f:
        workflow_data = yaml.safe_load(f.read())

    env_vars = workflow_data.get("env", {})

    assert "PYTHON_VERSION" in env_vars, "PYTHON_VERSION must be set"
    assert env_vars["PYTHON_VERSION"] == "3.13", "Python version must be 3.13"
    assert "REGISTRY" in env_vars, "REGISTRY must be set"
    assert env_vars["REGISTRY"] == "ghcr.io", "Registry must be ghcr.io"


def test_ci_cd_documentation_exists() -> None:
    """Test that CI/CD documentation exists."""
    doc_path = PROJECT_ROOT / "docs/ci-cd-guide.md"
    assert doc_path.exists(), "CI/CD documentation must exist"

    with open(doc_path) as f:
        content = f.read()

    # Check for required sections
    assert "## Pipeline Architecture" in content, "Must document pipeline architecture"
    assert "## Environment Variables and Secrets" in content, (
        "Must document env vars and secrets"
    )
    assert "## Troubleshooting Guide" in content, "Must include troubleshooting guide"
    assert "## Manual Deployment Override Procedures" in content, (
        "Must document manual procedures"
    )
