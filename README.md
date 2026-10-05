# AI301 Unit 4 starter: pr-precheck

Materials for Unit 4 of AI301 (test and submit). This repo holds the
week's runnable artifacts: the pr-precheck tool shell and its eval
harness. All instructions live on the course portal (Overview,
Activity, and Check-In tabs for Unit 4); this repo is the package those
pages tell you to install and build out.

## What's here

- `skill/`: the pr-precheck tool as empty structured templates plus a
  fixed interface: read `skill/CONTRACT.md` first, top to bottom. The
  layout and the contract are given; the content of every file is
  yours: `SKILL.md`, the rubric, the evidence guide, the procedure
  (your voice guide pastes forward from Unit 2, and the sandbox
  `scope.md` comes written except its `Repo:` line, which you
  fill). Building the whole tool is the Unit 4 deliverable.
- `eval/`: the eval harness, the gold labels, and 24 frozen packages
  (20 scored plus the 4 calibration packages from the in-class
  activity). See `eval/README.md` for the full run and output guide.

## Install the tool shell

Copy the whole `skill/` folder to `~/.claude/skills/pr-precheck/`
(create the folders if they do not exist). Build your tool inside that
installed copy and point the harness at it, so eval runs and live runs
share one canonical tool.

## Run the eval

From `eval/`, with the Claude Code CLI installed:

    python3 run_eval.py --skill path/to/your/tool-directory

`--limit 3` gives a smoke run. Full docs: `eval/README.md`.
