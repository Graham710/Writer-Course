---
name: test
description: Run the pytest suite and report results
---

# /test -- Run Project Tests

Run the full test suite and report results.

## Steps
1. Run `pytest tests/ -v --tb=short` from the project root
2. If any tests fail, show the failing test name, the assertion error, and the relevant source file
3. If all tests pass, confirm the count
4. Do NOT modify any files -- this is a read-only diagnostic
