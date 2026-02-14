#!/bin/bash
# Auto-format Python files with ruff after edits.
set -e

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" == *.py ]]; then
  if command -v ruff &> /dev/null; then
    ruff format "$FILE_PATH" 2>/dev/null || true
    ruff check --fix "$FILE_PATH" 2>/dev/null || true
  elif command -v uv &> /dev/null; then
    uv run ruff format "$FILE_PATH" 2>/dev/null || true
    uv run ruff check --fix "$FILE_PATH" 2>/dev/null || true
  fi
fi

exit 0
