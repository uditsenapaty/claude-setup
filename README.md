# claude-setup

My Claude Code research setup: a `CLAUDE.md` source-of-truth, a `claude-setup.py` installer, and a
`skills/` folder of focused ML-research skills that get installed as `custom-skills`.

## Layout

```
claude-setup/                       # this repo
├── CLAUDE.md                       # copy to your project root (source of truth)
├── claude-setup.py                 # one-shot installer
└── skills/                         # becomes .claude/skills/custom-skills/ after install
    ├── ml-research-queries/        # ORCHESTRATOR — entry point, owns state files + intake
    │   ├── SKILL.md
    │   ├── assets/                 # research-status.template.md, research-index.template.md
    │   └── references/intake-bank.md
    ├── ml-content-researcher/      # literature / SOTA / gap (token-efficient)
    ├── ml-experiment-designer/     # minimal conclusive experiments + ablations within budget
    ├── ml-pipeline-architect/      # architecture, folder-depth enforcement, backbone wiring
    ├── ml-deterministic-checks/    # dry-run verification vs full-on-target runs
    └── ml-results-synthesizer/     # results tables + conclusions tied to goals
```

## One-time install (per project)

```bash
# clone thie repo in project root
git clone https://github.com/UzzyDizzy/claude-setup.git
# from your project root
python ./claude-setup/claude-setup.py
# then drop CLAUDE.md into the project root
cp ./claude-setup/CLAUDE.md ./CLAUDE.md
```

`claude-setup.py` clones the 5 skill repos into `.claude/skills/` (gstack, gsd, superpowers,
anthropic, custom-skills), runs gstack's `./setup`, and installs the global codebase tools
(graphify, understand-anything) if missing. Re-runnable; `--force` re-clones. See the header of the
script for flags, and **confirm the graphify / understand-anything install commands in its CONFIG**
— those two are placeholders until you set your real install method.

## How a session flows

1. Invoke **ml-research-queries** (or just say "let's research X" / "resume").
2. It creates/loads `./research-status.md`, runs graphify/understand-anything, and asks the gating
   questions for the current phase only — never all at once, never twice.
3. As objectives sharpen, it routes to the specialist skills (research → design → architect → verify
   → synthesize) and updates `research-status.md` (every prompt) and `research-index.md` (every run).
4. `CLAUDE.md` holds the decisions that stick.

> State files live in the **project root**, not in `skills/`, because the skill repos are re-cloned
> each session and that would wipe in-folder state.
