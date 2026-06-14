---
name: ml-research-queries
description: >-
  MANDATORY entry point for any ML/DL research work. Use the moment the user asks to start, resume,
  plan, or continue research, an experiment, a paper reproduction, a benchmark/dataset build, or a
  model/pipeline build — even a bare "let's research X", "continue", "resume", or "help me build a
  model". It loads/refreshes the project state file (research-status.md), decides scratch-vs-resume,
  runs the codebase-understanding step (graphify / understand-anything), and asks the right intake
  questions at the right phase WITHOUT re-asking what is already answered. Always consult this before
  writing any research code, so work stays budget-aware, deterministic, and converges to a conclusion.
  Routes to ml-content-researcher, ml-experiment-designer, ml-pipeline-architect,
  ml-deterministic-checks, and ml-results-synthesizer as phases progress.
---

# ML Research Queries — project orchestrator

This skill is the control loop for a research project. It does three jobs: (1) keep a durable
**state file** so nothing is re-asked, (2) ask intake questions **as objectives sharpen**, not all
at once, and (3) hand off to the specialist skills. The north star: every session moves the project
**concisely toward a conclusive deliverable** within budget.

## State files (read this first)

Two files hold project memory. They live in the **project root**, NOT inside this skill folder:

| File | Path | When written |
|------|------|--------------|
| `research-status.md` | `./research-status.md` | **After every prompt** (mandatory) |
| `research-index.md`  | `./research-index.md`  | **After every completed execution** (mandatory) |

Templates are bundled here: `assets/research-status.template.md`, `assets/research-index.template.md`.

> Why the project root and not this folder? The skill repos are re-cloned each session (`--depth 1`),
> which would wipe any state stored inside them. Project-root files survive and stay tied to the
> repo. On first run, copy the templates out to the project root. If you genuinely need them
> elsewhere, that's a one-time decision to record in the status file's Decisions Log.

## First action, every invocation

1. Check for `./research-status.md`.
   - **Missing → SCRATCH.** Copy both templates to the project root. Go to *Bootstrap*.
   - **Present → RESUME.** Read it. Print a 3-line recap: `type · current phase · selected goals`.
     Then go to *Refresh*, then ask only the next unanswered question for the current phase.
2. Never dump all questions in one message. Ask the **smallest gating set** for the current phase
   (≤3 questions), proceed, and defer the rest with a trigger noted in the status file.

## Bootstrap (scratch only) — ask in this order, one small batch at a time

**Batch A — orientation + framing** (ask together):
- Scratch vs understand-an-existing-repo, and which codebase tool to run: **graphify** or
  **understand-anything** (see *Refresh* for how the artifact is stored).
- Research **type** (Q2): architecture/framework pipeline · conclusion-via-experiments ·
  benchmark/dataset creation — one or a combination.
- **Topic / research gap** (Q9): the specific gap to close.

**Batch B — constraints** (ask after A is answered):
- **Budget** (Q3): GPUs (type/count/hours), APIs (which/credits), total credit or cost ceiling, and
  whether the **target system is available now** (decides verification mode later).
- **Folder-depth policy** (Q4): max nesting for *code* (0 = everything in root: `config.py`,
  `models.py`, …; 1 = one level of subfolders; etc.). `data/`, `saved_models/`, `checkpoints/`,
  `logs/`, and similar artifact dirs are exempt and may nest freely.

Record every answer in `research-status.md` immediately, then continue to *Goal discovery*.

## Refresh (resume) and the codebase-understanding rule

The codebase-understanding artifact (a graphify wiki or an understand-anything markdown) must be
**(a) created at start** and **(b) refreshed after each new prompt that changed code**, then its path
and refresh time stored in the status file under *Orientation*. Prefer re-running the tool the user
already chose; only switch tools if the user asks. Treat this artifact as the factual map of the repo
when deriving goals and the index — do not invent file/function names that aren't in it or on disk.

> These two tools are set up by `claude-setup.py` but are **different kinds of thing**:
> - **graphify** is a global CLI (a `uv`/pip tool, command `graphify`). Invoke it like any shell
>   command and read the wiki it writes.
> - **understand-anything** is a **Claude Code plugin** (added via `/plugin marketplace add` +
>   `/plugin install understand-anything`), not a PATH binary. Use it through its plugin
>   command/skill inside this session, not via a shell call.
>
> This skill does not wrap either tool's flags — run each the way the user runs it and store the
> resulting artifact path + timestamp under *Orientation*.

## Phase cadence — what to ask, and when

Ask each item once, when its phase becomes active. Mark deferred items in the status file with their
trigger so they are never forgotten.

| Phase | Becomes active when… | Ask / do | Hand off to |
|-------|----------------------|----------|-------------|
| 0 Orientation | first invocation | scratch/resume + run graphify/understand-anything | — |
| 1 Framing | scratch bootstrap | type (Q2), topic (Q9), budget (Q3), depth (Q4) | — |
| 2 Goal discovery | framing done | derive candidate goals (Q10) from topic + codebase artifact; ask which to target (multiple allowed; user may add their own) | `ml-content-researcher` for gap/SOTA grounding |
| 3 Experiment design | a goal is selected | # conclusive experiments, # ablations per pipeline, specific settings (Q5, experiment side) | `ml-experiment-designer` |
| 4 Architecture | building begins | complexity, must-have / must-NOT-have, tech-merge idea, success criteria (Q5, architecture side); backbone? (Q6) | `ml-pipeline-architect` |
| 5 Implementation | architecture agreed | write code under the depth policy; update `research-index.md` after each run | `ml-pipeline-architect`, `ml-deterministic-checks` |
| 6 Verification | code exists | deterministic-only vs full-on-target run (Q7) | `ml-deterministic-checks` |
| 7 Conclusion | experiments produce numbers | tables, ablation deltas, claims tied to goals | `ml-results-synthesizer` |

Exact wording, options, and follow-ups for Q1–Q10 are in **`references/intake-bank.md`** — read it
when you need the precise phrasing or the backbone/model sub-questions (Q6 has open-source-only rules
and api-vs-local branches).

## Mandatory update rules

- **After every prompt:** open `research-status.md`, bump `Session`/timestamp, write any new answers,
  append any irreversible decision to the Decisions Log, and update the refresh time if the codebase
  artifact was regenerated. This is what makes "never re-ask" true.
- **After every completed execution** (a prompt that produced/changed files or ran experiments):
  update `research-index.md` — folder map (depth-limited), file purposes, key function/entry-point
  paths, and any experiment row with its result artifact.
- Stored answers are **changeable only when the user says so explicitly**. If a new request conflicts
  with a stored decision, surface the conflict and ask before overwriting.

## Operating discipline (matches CLAUDE.md)

- **Planning mode → research-exhaustive.** Before committing to an architecture or experiment set,
  ground goals in the literature and the codebase artifact; surface trade-offs; pick the *minimum*
  experiment set that can actually settle the question.
- **Execution mode → deterministic.** Default to deterministic checks (`ml-deterministic-checks`).
  Run full heavy jobs only when the target system is available now (per budget answer).
- Keep messages concise. State assumptions inline rather than asking a fifth clarifying question when
  the answer is already in `research-status.md` or the codebase artifact.
