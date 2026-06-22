# Deli AutoResearch

Distributable implementation of [Deli Chen's AutoResearch](https://victorchen96.github.io/) workflow — long-horizon autonomous survey writing with anti-loop orchestration, heartbeat watchdogs, and five paper sub-skills.

**For coding agents:** read [`AGENTS.md`](AGENTS.md) first.

## Features

- Protocol framework (`Deli_AutoResearch/SKILL.md`) — zero-interaction, stall detection, 3-layer heartbeat
- Paper-writing skill group split into 5 routable sub-skills
- Python tools for arXiv search, LQS scoring, citation verify, gates, LaTeX compile, API review
- Task scaffolding via `init_task.py`
- Example task at `tasks/_example/`

## Install

```bash
git clone <this-repo>
cd AutoResearch
# Windows:
powershell -File scripts/bootstrap.ps1
# macOS/Linux:
bash scripts/bootstrap.sh
```

Optional: [TeX Live](https://tug.org/texlive/) or MiKTeX for `compile_paper.py`.

## Start a research task

```bash
python tools/init_task.py continual-learning --topic "Continual Learning for LLM Agents"
```

Edit `tasks/continual-learning/state/task_spec.md` — set **Scope**, **Angle**, **Audience**.

## Run the workflow (Cursor)

1. Open `Deli_AutoResearch/orchestrator/loop_prompt.md`
2. Replace `{{REPO_ROOT}}` with your clone path (e.g. `C:\Users\you\AutoResearch`)
3. Paste the loop block into Cursor **`/loop 2h`**
4. Agent launches fresh work subagents each tick per `skills/router.md`

### Watchdog (recommended)

**Windows** (separate terminal):

```powershell
.\Deli_AutoResearch\watchdog\L0_shell_guard.ps1
```

**macOS/Linux:**

```bash
chmod +x Deli_AutoResearch/watchdog/L0_shell_guard.sh
./Deli_AutoResearch/watchdog/L0_shell_guard.sh
```

Hourly L1 patrol: use `Deli_AutoResearch/watchdog/L1_cron_prompt.md` in Cursor cron.

## Tools reference

| Command | Purpose |
|---------|---------|
| `python tools/init_task.py <slug> --topic "..."` | Scaffold new task |
| `python tools/stall_detector.py tasks --scan` | Find stalled tasks |
| `python tools/update_progress.py tasks/<slug> --iteration` | End-of-iteration update |
| `python tools/check_gates.py tasks/<slug>` | Quality gates 1–5 |
| `python tools/search_arxiv.py 'all:"topic"' -o out.json` | Literature stage 1 |
| `python tools/lqs_score.py candidates.json -o scored.json` | LQS scoring |
| `python tools/verify_citations.py batch.json` | Verify ≤20 citations |
| `python tools/compile_paper.py tasks/<slug>/paper` | Build PDF |
| `python tools/call_api.py --summary-file paper/review_input.md` | Peer review (needs API key) |

## Directory layout

```
AutoResearch/
├── AGENTS.md                 # Agent onboarding (start here)
├── README.md
├── requirements.txt
├── Deli_AutoResearch/
│   ├── SKILL.md              # Framework protocol
│   ├── orchestrator/         # /loop prompts
│   ├── watchdog/             # L0/L1 guards
│   ├── prompts/              # Subagent patterns A–D
│   └── skills/               # paper-writing + 5 sub-skills + router
├── tools/                    # CLI utilities
├── templates/task/           # init_task template
└── tasks/
    └── <your-slug>/          # state/, paper/, logs/
```

## API keys (peer review & experiments)

```bash
export OPENAI_API_KEY=sk-...
# optional:
export OPENAI_BASE_URL=https://api.openai.com/v1
export AUTORESEARCH_MODEL=gpt-4o
```

## License

Framework protocol per Deli Chen's open-source AutoResearch release. Tools in `tools/` are MIT-friendly utilities for local agent use.
