#!/bin/bash
# format-python.sh
# Auto-format Python files after editing

# Log to a file for debugging
LOG_FILE="/home/ryan/.claude/hooks/format-python.log"
echo "[$(date)] Hook triggered" >> "$LOG_FILE"

# Write to stderr to ensure visibility
echo "🐍 Python formatter hook triggered" >&2

# Read JSON input from stdin
input=$(cat)
echo "Raw input: $input" >> "$LOG_FILE"

# Extract file paths from JSON input
if [ -n "$input" ]; then
  # Try to extract file_path or file_paths from the JSON
  file_path=$(echo "$input" | jq -r '.tool_output.file_path // .tool_input.file_path // empty' 2>/dev/null)

  if [ -z "$file_path" ]; then
    # Try CLAUDE_FILE_PATHS environment variable as fallback
    file_path="$CLAUDE_FILE_PATHS"
  fi

  echo "Extracted file_path: $file_path" >> "$LOG_FILE"
else
  file_path="$CLAUDE_FILE_PATHS"
fi

# Check if we have a file path
if [ -z "$file_path" ]; then
  echo "No file path found, exiting" >> "$LOG_FILE"
  exit 0
fi

# Check if it's a Python file
if [[ "$file_path" =~ \.py$ ]]; then
  echo "Processing Python file: $file_path" >> "$LOG_FILE"

  # Check if file exists
  if [ -f "$file_path" ]; then
    echo "File exists, formatting..." >> "$LOG_FILE"

    # Get the directory of the file
    file_dir=$(dirname "$file_path")

    # Find project root - look for the topmost directory with .venv
    project_root="$file_dir"
    found_venv=""

    # Search upwards for all .venv directories
    temp_dir="$file_dir"
    while [ "$temp_dir" != "/" ]; do
      if [ -d "$temp_dir/.venv" ]; then
        found_venv="$temp_dir"
      fi
      temp_dir=$(dirname "$temp_dir")
    done

    # Use the topmost .venv directory found
    if [ -n "$found_venv" ]; then
      project_root="$found_venv"
    else
      # If no .venv found, try pyproject.toml
      temp_dir="$file_dir"
      while [ "$temp_dir" != "/" ]; do
        if [ -f "$temp_dir/pyproject.toml" ]; then
          project_root="$temp_dir"
          break
        fi
        temp_dir=$(dirname "$temp_dir")
      done
    fi

    echo "Project root: $project_root" >> "$LOG_FILE"
    echo "File directory: $file_dir" >> "$LOG_FILE"

    # Run ruff check with fixes
    ruff_check_output=""
    ruff_format_output=""
    has_issues=false

    if command -v uv &> /dev/null; then
      echo "Using uv run ruff" >> "$LOG_FILE"

      # Run ruff check from project root
      cd "$project_root" || exit 1
      ruff_check_output=$(uv run ruff check --fix "$file_path" 2>&1)
      ruff_check_exit=$?
      echo "$ruff_check_output" >> "$LOG_FILE"

      # Run ruff format
      ruff_format_output=$(uv run ruff format "$file_path" 2>&1)
      ruff_format_exit=$?
      echo "$ruff_format_output" >> "$LOG_FILE"

    elif command -v ruff &> /dev/null; then
      echo "Using ruff directly" >> "$LOG_FILE"

      # Also run from project root for consistency
      cd "$project_root" || exit 1

      # Run ruff check
      ruff_check_output=$(ruff check --fix "$file_path" 2>&1)
      ruff_check_exit=$?
      echo "$ruff_check_output" >> "$LOG_FILE"

      # Run ruff format
      ruff_format_output=$(ruff format "$file_path" 2>&1)
      ruff_format_exit=$?
      echo "$ruff_format_output" >> "$LOG_FILE"
    fi

    # Display ruff output if there were changes or issues
    if [[ "$ruff_check_output" == *"Found"* ]] || [[ "$ruff_format_output" == *"reformatted"* ]]; then
      has_issues=true
      echo "" >&2
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
      echo "🔧 Ruff Analysis Results:" >&2
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2

      if [[ "$ruff_check_output" == *"Found"* ]]; then
        echo "📋 Linting: $ruff_check_output" >&2
      fi

      if [[ "$ruff_format_output" == *"reformatted"* ]]; then
        echo "✨ Formatting: Code style automatically fixed" >&2
      fi
    fi

    # Run mypy type checking
    mypy_output=""
    mypy_exit_code=0

    # Ensure we're in the project root for mypy
    cd "$project_root" || exit 1

    if command -v uv &> /dev/null; then
      echo "Running mypy with uv from project root: $project_root" >> "$LOG_FILE"
      mypy_output=$(uv run mypy "$file_path" 2>&1)
      mypy_exit_code=$?
    elif command -v mypy &> /dev/null; then
      echo "Running mypy directly" >> "$LOG_FILE"
      mypy_output=$(mypy "$file_path" 2>&1)
      mypy_exit_code=$?
    else
      echo "mypy not found, skipping type checking" >> "$LOG_FILE"
    fi

    # Log mypy output
    if [ -n "$mypy_output" ]; then
      echo "$mypy_output" >> "$LOG_FILE"
    fi

    # If mypy found errors, display them to the user
    if [ $mypy_exit_code -ne 0 ] && [ -n "$mypy_output" ]; then
      echo "" >&2
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
      echo "🔍 MyPy Type Checking Results:" >&2
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
      echo "$mypy_output" | grep -E "(error:|note:)" | sed 's/^/  /' >&2

      # Also write to a temporary file for visibility
      MYPY_RESULT_FILE="/tmp/mypy_result_$(basename "$file_path").txt"
      echo "MyPy found type errors in $file_path:" > "$MYPY_RESULT_FILE"
      echo "$mypy_output" | grep -E "(error:|note:)" >> "$MYPY_RESULT_FILE"
      echo "Saved MyPy results to: $MYPY_RESULT_FILE" >&2

      has_issues=true
    fi

    # Show summary message if there were any issues
    if [ "$has_issues" = true ]; then
      echo "" >&2
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
      echo "✅ File saved | 🔧 Auto-fixes applied where possible" >&2
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
      echo "" >&2
    else
      # No issues found
      echo "" >&2
      echo "✅ Python file processed - All checks passed!" >&2
      echo "" >&2
    fi

    echo "Formatting and type checking complete" >> "$LOG_FILE"
  else
    echo "File does not exist: $file_path" >> "$LOG_FILE"
  fi
else
  echo "Not a Python file: $file_path" >> "$LOG_FILE"
fi

exit 0
