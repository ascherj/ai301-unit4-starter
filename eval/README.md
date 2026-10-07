# Eval set and harness

20 scored PR packages, 4 unscored calibration packages from the class
activity, instructor gold labels, and a runnable harness that grades
any pr-precheck tool directory against the set.

## The one command

From this directory, with the Claude Code CLI installed (you have it
if you have been building skills):

    python3 run_eval.py --skill path/to/your/tool-directory

Point `--skill` at the directory holding your filled tool (your
installed copy at `~/.claude/skills/pr-precheck/` once you have
written the four files). The harness inlines `SKILL.md`, `rubric.md`,
`procedure.md`, and `references/evidence-guide.md` from the
contract's fixed paths; `scope.md` and `voice-guide.md` never enter
an eval run, by design. The shipped templates in `../skill/` are
empty on purpose, and the tool refuses to run without your frame,
your checks, your verdict rule, your evidence map, and your
procedure: write them first.

`--rubric path/to/rubric.md` still works as an alias from earlier
weeks: it means "the tool directory is this file's parent".

Useful flags: `--limit 3` for a quick smoke run, `--only
pkg-07,pkg-12` to re-grade just the named packages, `--workers N` to
change parallelism (default 5), `--include-calibration` to also grade
the four worksheet packages (they are never scored), `--out
results.json` to keep the full per-check results.

`--only` is the flag for the revise loop: when a full run disagrees on
two packages, re-run only those two while you adjust your components
(about $0.25 per package instead of about $5 for a full run), then
confirm with one full run at the end. Partial runs never print a bar
verdict; only a full 20-package run can pass.

Partial runs also cannot show the category floor, and a revision that
loosens a check can flip a package that agreed before. So when a
revision loosens a check, add canaries to the `--only` list: one
already-agreeing package from each small category the change could
touch (the 2-package `standards-wall` category is the live case), so
a flip shows up at $0.25 instead of on your confirming full run. The
output table's `category` column names each package's category, so
pick canaries straight from your last full run's table: any row in
the right category whose `agree` column says `yes`.
`--include-calibration` composes with `--only`, so a calibration
package your class already resolved works as a free trap check too
(calibration packages carry no score; their agreement shows per item
in the table).

Every run grades with Sonnet, the course's standard model; there is no
model flag. This keeps every student's run (and the instructor
stability runs that set the bar) on the same grader, and Sonnet is the
model your course credit is budgeted for.

## Saving the run you commit

Add `--save-run eval-run.txt` to your confirming full run and the harness
writes the file for you:

    python3 run_eval.py --skill path/to/your/tool-directory --save-run eval-run.txt

The file holds the same text you watched on screen, written as UTF-8 on
every platform, under a short header the harness fills in: the pinned
model, the tool it graded, and a fingerprint of each file that went into
the run. That file is what you upload to your course repo.

Partial runs refuse to write it. A `--limit` or `--only` run says so and
leaves the file untouched, so a cheap re-run can never overwrite the full
run you already saved.

Do not hand-edit the file. Where you account for the runs it took to get
there is your write-up in the phase file, not the transcript.

## What the output means

One line per package while grading, then a table:

    item    category      gold    verdict  agree  note
    pkg-02  clear-accept  accept  accept   yes
    pkg-06  silent-drift  reject  accept   NO     graded accept
    ...
    categories: clear-accept 7/7  not-tested 4/4  silent-drift 4/4  standards-wall 1/2  unreviewable 3/3
    agreement: 19/20 scored items  (bar: 18/20: PASS)

- `category` is the package's composition category, matching the
  `categories:` tally line and the Grading tab's composition table
  (calibration packages show `calib`). This column is where canary
  packages come from.
- `gold` is the instructor label from `gold-labels.json`.
- `verdict` is what the tool decided with YOUR frame, rubric,
  evidence guide, and procedure.
- The `note` column names the checks your tool failed the package
  on, which is where to look when you disagree with a gold label.
- The `categories` line tallies matches per eval-set composition
  category. Passing needs at least one match in every category (the
  category floor): one match, not all, which is why the sample
  above still shows PASS with `standards-wall 1/2`. It exists
  because a tool that cannot see a whole category, however
  well it does elsewhere, is missing a check the set was built to
  force. The 2-package `standards-wall` category is the live case
  this week: with only two packages, a rubric with no standards
  checks cannot buy the misses back on volume. Partial runs print
  the tallies for just the packages graded, plus a reminder that
  only a full run decides the bar and the floor.
- The agreement line is the score the grading bar reads. The bar:
  agreement of 18 of 20 or better passes (exactly 18 passes), AND the
  category floor holds. The 4 calibration packages are never scored.
  Full bar details, including the human read of your tool: the
  Assignment tab for this unit on the course portal.

Disagreements are the feedback loop: open the package the table
names, reread the diff against the plan and the evidence against the
test plan, and decide whether your rubric's pass condition, your
evidence map, your procedure, or your frame is what needs to move.
Then re-run; retries are unlimited.

## What is in a package

Each `packages/*.md` file is self-contained: a real issue's context
(title, body excerpt, thread highlights, and a repo-facts block with
the repo's stated PR-template asks and contribution policy, including
any AI-use policy), a plan-context block (the accepted plan the PR
claims to implement, in the week-3 form, with the repro evidence it
built on), and the candidate PR (title, description, commit list,
unified diff, and test evidence), all frozen on the capture date
stamped at the top. The issue contexts are real; every plan, diff,
PR text, and evidence block is instructor-authored, so no real
stranger's writing is ever graded here. The harness never touches
GitHub; the tool grades the bundle text, so every run sees the same
world and your score cannot drift because a thread moved on.

Every bundle also has a `.json` twin with the same frozen content in
structured form (issue, thread highlights, repo facts, plan context,
and the PR's title, description, commits, diff, and test evidence as
fields). Read whichever you prefer; they are the same snapshot.
`packages_to_json.py` regenerates the JSON from the markdown.

## Do not grade the live issue

The `source:` line in each package names the real issue
(`owner/repo#number`). It is deliberately not a link: the real issue
has kept moving since the capture date, with new comments, new linked
PRs, sometimes a fix already merged. That is exactly why the
snapshots exist. The gold labels describe the snapshot, not today's
GitHub. When the live page and the bundle disagree, the bundle wins.

## Format note

This markdown-plus-manifest layout is the browsable form of the
eval-set format used in production model evals: one record per item
with input, gold label, and metadata (usually JSONL), a judge prompt
(here, your whole tool), and a scoring script (here, `run_eval.py`).
Fourth week on the same instrument: the judged artifact is now a
whole pull request, and the judge is a tool you built end to end.
