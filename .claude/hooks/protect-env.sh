#!/bin/bash
# Block Read/Edit/Write access to .env files containing API secrets.
set -e

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" == *".env" ]] && [[ "$FILE_PATH" != *".env.example" ]]; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ".env contains API secrets and cannot be read or modified"
    }
  }'
  exit 0
fi

exit 0
