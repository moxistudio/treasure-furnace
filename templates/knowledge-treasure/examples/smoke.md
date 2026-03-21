# Smoke Test: knowledge-treasure

Treasure ID used in this test: `support-policy`

## Input

```text
What is our escalation path for a severity-1 outage, and what should happen in the first 30 minutes?
```

## Expected Checks

1. answer references the best matching policy context
2. response includes concrete first-step actions
3. uncertain or missing policy details are marked as "to-be-verified"
4. no fabricated source titles or links

## Local Run Placeholder

```bash
treasure-furnace smoke --path community/support-policy --example examples/smoke.md
```

