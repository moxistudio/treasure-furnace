# Smoke Test: marshal-treasure

Treasure ID used in this test: `weekly-report-helper`

## Input

```text
Create this week's report from team activity logs. Keep it short and include: outcomes, in-progress, risks, next actions.
```

## Expected Checks

1. output has all requested sections
2. each section is actionable and concise
3. missing data is explicitly marked, not fabricated
4. report remains stable in structure across repeated runs

## Local Run Placeholder

```bash
treasure-furnace smoke --path community/weekly-report-helper --example examples/smoke.md
```

