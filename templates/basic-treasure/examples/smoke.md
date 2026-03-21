# Smoke Test: basic-treasure

Treasure ID used in this test: `email-polisher`

## Input

```text
Rewrite this update into a concise status note:
"We finished API migration for reporting, fixed two blocker bugs, and need one more day for dashboard QA."
```

## Expected Checks

1. returns a clear short status message
2. includes completed work and remaining work
3. does not invent extra facts
4. stays concise and readable

## Local Run Placeholder

```bash
treasure-furnace smoke --path community/email-polisher --example examples/smoke.md
```

