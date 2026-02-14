---
name: add-unit
description: Add a new unit to the course curriculum
disable-model-invocation: true
---

# /add-unit -- Add a New Course Unit

Add a new unit to the Writer Course curriculum.

## Required inputs (ask user if not provided)
- Unit title
- Start page and end page in the PDF
- 3 learning objectives (actionable, starting with a verb)

## Steps
1. Determine the next sequential unit ID by reading `src/unit_catalog.py` and finding the last entry in `RAW_UNITS`
2. Add a new dict entry to `RAW_UNITS` in `src/unit_catalog.py`, matching the existing format:
   ```python
   {
       "id": "<next_id>",
       "title": "<title>",
       "start_page": <start>,
       "end_page": <end>,
       "learning_objectives": [
           "<obj1>",
           "<obj2>",
           "<obj3>",
       ],
   },
   ```
3. Delete `data/units.json` and `data/exercises.json` so caches rebuild on next app launch
4. Run `pytest tests/test_units.py -v` to verify the unit map still loads correctly
5. Confirm: the chunk cache (`data/chunks.json`) will rebuild automatically on next `streamlit run`

## Invariants to maintain
- Unit IDs must be sequential string integers ("0", "1", "2", ...)
- Page ranges must not overlap with existing units
- Each unit must have exactly 3 learning objectives
- Learning objectives must be actionable (start with a verb)
