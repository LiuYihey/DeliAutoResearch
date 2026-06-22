# loop-engineering-skill

Agent skill for designing and scaffolding **autonomous loop frameworks** — file-backed state, orchestrator ticks, stall detection, fresh sessions, and quality gates for any long-horizon task.

Inspired by [loop engineering](https://victorchen96.github.io/auto_research/framework.html) patterns (e.g. Deli AutoResearch), packaged for the [Agent Skills](https://agentskills.io/) ecosystem.

## Install

```bash
# Standalone repo (after published to GitHub)
npx skills add LiuYihey/loop-engineering-skill -a cursor -y

# From DeliAutoResearch monorepo subpath (available now)
npx skills add https://github.com/LiuYihey/DeliAutoResearch/tree/main/loop-engineering-skill -a cursor -y

# Global install
npx skills add LiuYihey/loop-engineering-skill -a cursor -g -y

# List skills in this repo without installing
npx skills add LiuYihey/loop-engineering-skill --list
```

Works with **Cursor**, Claude Code, Codex, and [68+ agents](https://github.com/vercel-labs/skills) via [skills CLI](https://skills.sh).

## What it does

Given a user goal (migrate a codebase, write a content series, run benchmarks, fix lint debt, etc.), the agent:

1. **Intake** — goal, deliverables, success criteria
2. **Classify** — pick a task archetype (`code-build`, `content-pipeline`, …)
3. **Design** — phases, metrics, gates, router
4. **Scaffold** — `loops/<slug>/` workspace with orchestrator prompt for `/loop`
5. **Handoff** — how to start, monitor, and stop

## Skill structure

```
skills/loop-engineering/
├── SKILL.md              # Main protocol
├── reference/            # Archetypes + state contract
├── templates/            # Loop workspace templates
├── scripts/              # init_loop.py, stall_scan.py, update_progress.py
└── examples/             # End-to-end walkthrough
```

## Quick try (after install)

In Cursor Agent chat:

```
@loop-engineering Turn "migrate our Express API to FastAPI with tests" into an overnight loop
```

Or bootstrap manually from the installed skill directory:

```bash
python .cursor/skills/loop-engineering/scripts/init_loop.py my-task \
  --goal "Your one-line goal" \
  --workspace loops \
  --archetype code-build \
  --cadence 2h
```

## Task archetypes

| Archetype | Example use |
|-----------|-------------|
| `code-build` | Features, services, CLIs |
| `refactor-hygiene` | Migrations, lint cleanup |
| `research-eval` | Compare options, surveys |
| `content-pipeline` | Docs, blogs, courses |
| `data-pipeline` | ETL, labeling |
| `ops-automation` | CI, deploy scripts |
| `bug-hunt` | Repro → fix → regression |
| `creative-explore` | Architecture / design options |

## License

MIT — see [LICENSE](LICENSE).
