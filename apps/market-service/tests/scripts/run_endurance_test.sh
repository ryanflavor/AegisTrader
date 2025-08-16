#!/bin/bash
# Run endurance tests with clean output
# Usage: ./run_endurance_test.sh <test_module>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if test module is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <test_module>"
    echo "Example: $0 test_story1_2b_task12"
    exit 1
fi

TEST_MODULE="$1"

# Change to project directory
cd "$PROJECT_DIR"

# Load test environment and run endurance test with output filtering
echo "Running endurance test: $TEST_MODULE"
echo "NOTE: This test may run for several hours (24h for production simulation)"
source .env.test.local && \
    export ENABLE_CTP_GATEWAY=true && \
    uv run python -u "tests/endurance/${TEST_MODULE}.py" 2>&1 | \
    python -u tests/utils/output_filter.py
