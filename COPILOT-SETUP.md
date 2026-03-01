# Sentinel-D — Copilot Setup for Dev B

## One-time setup

1. Copy everything in this folder into your Sentinel-D project root.

2. Edit `.copilot/config.json` — set your project start date:
   ```json
   { "projectStartDate": "2025-03-03" }
   ```

3. Set your model in Copilot CLI (first session only):
   ```
   copilot
   /model → select Claude Opus 4.6
   ```

## Every day

```bash
# Start your session
node .copilot/start-session.js

# Or specify a day manually
node .copilot/start-session.js --day=3
```

The script prints the exact prompt to paste into Copilot CLI.
Copilot then reads your identity file and today's goals automatically.

## File structure

```
.github/
  copilot-instructions.md   ← Your permanent identity as Dev B
                              (loaded automatically by Copilot every session)

.copilot/
  config.json               ← Your start date and preferences
  start-session.js          ← Run this each morning
  days/
    day-01.md               ← Day 1 tasks (Azure setup + schemas)
    day-02.md               ← Day 2 tasks (SRE Agent + DB clients)
    day-03.md               ← Day 3 tasks (Decision Gate + labelling)
    day-04.md               ← Day 4 tasks (Container App + DB wiring)
    day-05-08.md            ← Days 5-8 (SSIM, integration gate, Safety Governor, hardening)
    day-09-14.md            ← Days 9-14 (integration test, demo, write-up, submit)
```

## How Copilot loads your identity

`.github/copilot-instructions.md` is automatically read by GitHub Copilot
at the start of every session. It tells Copilot:
- You are Dev B, not Dev A
- Your exact component ownership
- The frozen schema contract with Dev A
- Your tech stack and coding style preferences
- Critical rules (KQL allowlist, audit log append-only, etc.)

The daily goal files are referenced explicitly in the session-starter prompt
using the `@filename` syntax, which pulls them into Copilot's context.

## Key shortcuts

| What | How |
|------|-----|
| Switch to Plan mode before coding | `Shift`+`Tab` |
| Pull a file into context | `@shared/schemas/validation_bundle.json` |
| Review all changes in session | `/diff` |
| Check before committing | `/review` |
| Switch model mid-session | `/model` |
| Check active model | `/status` |
| Rewind a bad edit | `Esc`+`Esc` |
