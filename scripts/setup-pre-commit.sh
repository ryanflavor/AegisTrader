#!/bin/bash
# Setup pre-commit hooks for the project

set -e

echo "🔧 Setting up pre-commit hooks..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
fi

# Install the pre-commit hooks
echo "🔗 Installing git hooks..."
pre-commit install
pre-commit install --hook-type commit-msg

# Run pre-commit on all files to check current status
echo "🧪 Running pre-commit on all files (this may take a moment)..."
pre-commit run --all-files || true

echo ""
echo "✅ Pre-commit hooks installed successfully!"
echo ""
echo "📋 Hooks that will run on every commit:"
echo "  - Black (Python formatter)"
echo "  - Ruff (Python linter)"
echo "  - MyPy (Type checker)"
echo "  - Security checks (detect-secrets, bandit)"
echo "  - File checks (trailing whitespace, YAML, JSON validation)"
echo "  - Shell script linting"
echo "  - Dockerfile linting"
echo "  - Commit message validation"
echo ""
echo "💡 Tips:"
echo "  - To run hooks manually: pre-commit run --all-files"
echo "  - To skip hooks temporarily: git commit --no-verify"
echo "  - To update hooks: pre-commit autoupdate"
echo ""
echo "⚠️  First commit might be slower as it downloads the hook dependencies."