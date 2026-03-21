---
name: Marshal Treasure Template
description: A production-style Treasure template for multi-step report workflows.
tools:
  - query_work_logs
  - llm_call
  - send_to_user
---

Use this template for multi-step Treasures that coordinate collection, drafting, and final output.

Use it for:

- weekly or monthly report generation
- multi-phase content production
- workflow-style operational summaries

Constraints:

- preserve a deterministic structure across runs
- do not invent metrics or completion claims
- surface missing inputs explicitly
- keep final output practical for decision-making

Output style:

- sectioned report
- clear risks and next actions
- no raw intermediate traces

