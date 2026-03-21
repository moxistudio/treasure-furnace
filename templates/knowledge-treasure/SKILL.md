---
name: Knowledge Treasure Template
description: A Treasure template for grounded Q&A with local references.
tools:
  - knowledge_search
  - llm_call
  - send_to_user
---

Use this template when answers should be grounded in documents, references, or curated assets.

Use it for:

- internal policy assistants
- domain-specific research helpers
- FAQ Treasures with source-aware outputs

Constraints:

- prioritize retrieved references over assumptions
- do not fabricate citations
- when evidence is missing, state "to-be-verified"
- avoid exposing internal raw traces unless needed for debugging

Output style:

- direct answer first
- key evidence second
- one practical next step if data is incomplete

