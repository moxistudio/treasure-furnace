# knowledge-treasure template

Use this template for Treasures that must search and cite knowledge context before answering.

## Good Fit

- policy and process Q&A
- domain research with references
- support knowledge helpers

## Required Extra Inputs

Add at least one knowledge source path used by your Treasure, for example:

- `knowledge/`
- `source/references/`
- `source/assets/`

## Customize

1. Copy and rename this directory to a hyphenated Treasure ID, for example `support-policy`.
2. Update `pack.yaml` metadata and activation intent.
3. Adjust `knowledge.source_dirs` to your real data layout.
4. Tune the prompt in `runtime.steps.compose_answer`.
5. Replace `examples/smoke.md` with a domain-relevant test.

## Local Validation Placeholder

```bash
treasure-furnace validate structure --path community/support-policy
treasure-furnace validate pack --file community/support-policy/pack.yaml
treasure-furnace validate skill --file community/support-policy/SKILL.md
treasure-furnace smoke --path community/support-policy --example examples/smoke.md
```

## Example Treasure IDs

- `deep-search`
- `ai-sentinel-briefing`

