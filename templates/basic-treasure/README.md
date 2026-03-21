# basic-treasure template

Use this template when you want a minimal Treasure with a single straightforward response flow.

## Good Fit

- quick helper Treasure
- summarization or rewrite assistant
- format conversion helper

## Customize

1. Copy this directory and rename it to your Treasure ID (hyphenated), for example `email-polisher`.
2. Update `pack.yaml` fields under `meta`, `activation`, and runtime prompt text.
3. Update `SKILL.md` constraints to match your domain.
4. Replace `examples/smoke.md` with your own test request and expected behavior.

## Local Validation Placeholder

```bash
treasure-furnace validate structure --path community/email-polisher
treasure-furnace validate pack --file community/email-polisher/pack.yaml
treasure-furnace validate skill --file community/email-polisher/SKILL.md
treasure-furnace smoke --path community/email-polisher --example examples/smoke.md
```

## Example Treasure IDs

- `deep-search`
- `weekly-report-helper`

