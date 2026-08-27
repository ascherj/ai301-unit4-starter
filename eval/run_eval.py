#!/usr/bin/env python3
"""Eval harness: grade every PR-package bundle with a pr-precheck tool
directory and score agreement against the gold labels.

One command:

    python3 run_eval.py --skill path/to/your/tool-directory

The tool directory is the contract's fixed layout: SKILL.md,
rubric.md, procedure.md, and references/evidence-guide.md are inlined
from those exact paths (scope.md and voice-guide.md never enter eval
mode, per the contract). `--rubric path/to/rubric.md` is accepted as
an alias meaning "the tool directory is this file's parent", so
harness commands from earlier weeks keep working against an installed
copy.

Requires the `claude` CLI (Claude Code). Each package is graded by one
non-interactive `claude -p` call carrying the tool's four files and
the bundle text; the model's last fenced JSON block is the verdict.

Every run grades with Sonnet (the course's standard model), regardless
of the local Claude Code default; the stated pass bar is only valid on
the model it was validated on.
"""

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = "sonnet"
JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

# The contract's fixed layout: file label -> path inside the tool dir.
TOOL_FILES = {
    "skill": "SKILL.md",
    "rubric": "rubric.md",
    "procedure": "procedure.md",
    "evidence": "references/evidence-guide.md",
}

PROMPT_TEMPLATE = """\
{skill}

----------------------------------------------------------------------
# Rubric (rubric.md)

{rubric}

----------------------------------------------------------------------
# Evidence guide (references/evidence-guide.md)

{evidence}

----------------------------------------------------------------------
# Procedure (procedure.md)

{procedure}

----------------------------------------------------------------------
# Eval package: {item_id}

{bundle}

----------------------------------------------------------------------
Run the pr-precheck skill above in EVAL MODE on this package bundle.
The bundle text is your only evidence; do not fetch or read anything
else, and ignore scope.md and voice-guide.md entirely (eval mode).
Execute the procedure as written, grade every check in the rubric
using the evidence guide's map, apply the rubric's verdict rule, and
end your reply with the fenced JSON block the skill's output format
requires, using "{item_id}" as the item id.
"""


def grade_one(item_id: str, bundle_path: Path, tool: dict[str, str],
              timeout: int) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        skill=tool["skill"], rubric=tool["rubric"],
        evidence=tool["evidence"], procedure=tool["procedure"],
        item_id=item_id, bundle=bundle_path.read_text(encoding="utf-8"))
    cmd = ["claude", "-p", "--model", MODEL]
    last_err = "no attempt"
    for _ in range(2):                       # one retry on bad output
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            last_err = f"timed out after {timeout}s"
            continue
        if proc.returncode != 0:
            last_err = f"claude exited {proc.returncode}: " \
                       f"{proc.stderr.strip()[:200]}"
            continue
        blocks = JSON_BLOCK_RE.findall(proc.stdout)
        if not blocks:
            snippet = " ".join(proc.stdout.split())[-160:]
            last_err = "no fenced JSON block in output" + \
                (f"; model output ended: ...{snippet}" if snippet else "")
            continue
        try:
            data = json.loads(blocks[-1])
        except ValueError as e:
            last_err = f"bad JSON: {e}"
            continue
        verdict = str(data.get("verdict", "")).lower()
        if verdict not in ("accept", "reject"):
            last_err = f"verdict is {verdict!r}, not accept/reject"
            continue
        failed = [c.get("name", "?") for c in data.get("checks", [])
                  if str(c.get("grade", "")).lower() != "pass"]
        return {"id": item_id, "verdict": verdict, "failed_checks": failed,
                "checks": data.get("checks", []), "error": None}
    return {"id": item_id, "verdict": None, "failed_checks": [],
            "checks": [], "error": last_err}


def _strip_scaffolding(text: str) -> str:
    """Drop HTML comments, YAML frontmatter, and fenced code blocks: the
    parts of a shipped template that are not the author's own content."""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    body = re.sub(r"\A---\n.*?\n---\n", "", body, flags=re.DOTALL)
    body = re.sub(r"^```.*?^```\s*$", "", body,
                  flags=re.DOTALL | re.MULTILINE)
    return body


def rubric_has_checks(text: str) -> bool:
    """True if any checks-table row carries a required/preferred weight."""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    for line in body.splitlines():
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[-1] in ("required", "preferred"):
            return True
    return False


def rubric_has_verdict_rule(text: str) -> bool:
    """True if the rubric carries prose outside comments, headings, and
    the checks table (a filled rubric states its verdict rule as plain
    text below the table)."""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return any(line.strip() and not line.lstrip().startswith(("#", "|"))
               for line in body.splitlines())


def doc_has_content(text: str) -> bool:
    """True if the doc carries prose beyond the template's headings (the
    shipped evidence-guide and procedure templates are headings plus
    comments)."""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return any(line.strip() and not line.lstrip().startswith("#")
               for line in body.splitlines())


def frame_has_content(text: str) -> bool:
    """True if SKILL.md carries the author's own instructions: prose
    beyond headings once comments, the frontmatter, and the shipped
    verbatim JSON schema block are stripped (the shipped frame template
    is exactly those parts)."""
    body = _strip_scaffolding(text)
    return any(line.strip() and not line.lstrip().startswith("#")
               for line in body.splitlines())


def resolve_tool_dir(a) -> Path | None:
    """--skill DIR wins; --rubric FILE means the tool dir is the file's
    parent, with the documented master-skill fallback: when FILE does not
    exist but a master-skill/ tool sits next to where it would be (the
    instructor layout), grade with that. Returns None on unusable args."""
    if a.skill:
        return Path(a.skill)
    rubric_p = Path(a.rubric)
    if rubric_p.is_file():
        return rubric_p.parent
    fallback = rubric_p.parent / "master-skill"
    if (fallback / "rubric.md").is_file():
        print(f"notice: {rubric_p} does not exist; grading with the "
              f"master tool at {fallback} (the master-skill fallback).")
        return fallback
    print(f"error: rubric not found at {rubric_p} and no master-skill/ "
          "directory sits next to it. Point --skill at your tool "
          "directory (or --rubric at the rubric.md inside it).",
          file=sys.stderr)
    return None


def load_tool(tool_dir: Path) -> dict[str, str] | None:
    """Read the four contract files, refusing politely on a missing or
    still-empty component (the shipped templates are empty on purpose)."""
    texts: dict[str, str] = {}
    for label, rel in TOOL_FILES.items():
        p = tool_dir / rel
        if not p.is_file():
            print(f"error: {p} not found. A pr-precheck tool directory "
                  "carries SKILL.md, rubric.md, procedure.md, and "
                  "references/evidence-guide.md at exactly these paths "
                  "(CONTRACT.md's layout); point --skill at the directory "
                  "holding your filled copies.", file=sys.stderr)
            return None
        texts[label] = p.read_text(encoding="utf-8")

    ok = True
    if not frame_has_content(texts["skill"]):
        print(f"error: {tool_dir / 'SKILL.md'} has no filled-in frame. The "
              "shipped template is headings, instruction comments, and the "
              "verbatim output schema; this week the frame's instructions "
              "are yours to write, and the tool cannot run without them. "
              "Write what each section must say (CONTRACT.md names the "
              "decisions), then re-run.", file=sys.stderr)
        ok = False
    if not rubric_has_checks(texts["rubric"]):
        print(f"error: {tool_dir / 'rubric.md'} has no filled-in checks. "
              "The shipped template is empty on purpose; the tool refuses "
              "to grade without a rubric. Write your checks and verdict "
              "rule first, then re-run.", file=sys.stderr)
        ok = False
    elif not rubric_has_verdict_rule(texts["rubric"]):
        print(f"error: {tool_dir / 'rubric.md'} has checks but no verdict "
              "rule. State below the checks table how the grades combine "
              "into accept or reject, including how unclear is treated; "
              "the template's Verdict rule section shows the shape. "
              "Without one, the grader invents its own combination rule "
              "and the run is wasted money.", file=sys.stderr)
        ok = False
    if not doc_has_content(texts["evidence"]):
        print(f"error: {tool_dir / 'references/evidence-guide.md'} has no "
              "filled-in content. The shipped template is family headings "
              "only; the tool needs your map of where evidence lives. "
              "Fill it, then re-run.", file=sys.stderr)
        ok = False
    if not doc_has_content(texts["procedure"]):
        print(f"error: {tool_dir / 'procedure.md'} has no filled-in "
              "content. The shipped template is stage headings only; the "
              "tool cannot grade without your procedure, and that is by "
              "design. Write the steps, then re-run.", file=sys.stderr)
        ok = False
    return texts if ok else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Grade the eval set with a pr-precheck tool directory "
                    "and score agreement.")
    ap.add_argument("--skill", default=None, metavar="DIR",
                    help="path to your tool directory (the contract's "
                         "fixed layout)")
    ap.add_argument("--rubric", default=None, metavar="FILE",
                    help="alias: the tool directory is this rubric.md's "
                         "parent (with a master-skill/ fallback when the "
                         "file does not exist)")
    ap.add_argument("--packages", default=str(HERE / "packages"))
    ap.add_argument("--gold", default=str(HERE / "gold-labels.json"))
    ap.add_argument("--include-calibration", action="store_true",
                    help="also grade the 4 worksheet calibration packages "
                         "(never scored)")
    ap.add_argument("--only", default=None, metavar="ID[,ID...]",
                    help="grade only these package ids, comma-separated "
                         "(e.g. --only pkg-07,pkg-12); cheap re-runs "
                         "while revising a component")
    ap.add_argument("--limit", type=int, default=0,
                    help="grade only the first N items (smoke runs)")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=420,
                    help="seconds per package per attempt")
    ap.add_argument("--out", default=None,
                    help="also write full results as JSON to this path")
    a = ap.parse_args()

    if not a.skill and not a.rubric:
        print("error: pass --skill DIR (your tool directory) or --rubric "
              "FILE (the rubric.md inside it).", file=sys.stderr)
        return 2
    tool_dir = resolve_tool_dir(a)
    if tool_dir is None:
        return 2
    if not tool_dir.is_dir():
        print(f"error: tool directory not found at {tool_dir}",
              file=sys.stderr)
        return 2
    tool = load_tool(tool_dir)
    if tool is None:
        return 2

    gold = json.loads(Path(a.gold).read_text(encoding="utf-8"))
    items = [it for it in gold["items"]
             if a.include_calibration or not it.get("calibration")]
    if a.only:
        wanted = [s.strip() for s in a.only.split(",") if s.strip()]
        known = {it["id"] for it in items}
        unknown = [w for w in wanted if w not in known]
        if unknown:
            print(f"error: --only ids not in the eval set: "
                  f"{', '.join(unknown)} (calibration packages need "
                  "--include-calibration)", file=sys.stderr)
            return 2
        items = [it for it in items if it["id"] in set(wanted)]
    if a.limit:
        items = items[:a.limit]
    if not items:
        print("error: no items to grade", file=sys.stderr)
        return 2

    packages_dir = Path(a.packages)
    missing = [it["id"] for it in items
               if not (packages_dir / f"{it['id']}.md").is_file()]
    if missing:
        print(f"error: bundle files missing: {', '.join(missing)}",
              file=sys.stderr)
        return 2

    print(f"grading {len(items)} package(s) with the tool at {tool_dir}, "
          f"model {MODEL}, {a.workers} worker(s)...", flush=True)
    results: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(a.workers) as pool:
        futs = {pool.submit(grade_one, it["id"],
                            packages_dir / f"{it['id']}.md",
                            tool, a.timeout): it["id"]
                for it in items}
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results[r["id"]] = r
            state = r["verdict"] or f"ERROR ({r['error']})"
            print(f"  {r['id']}: {state}", flush=True)

    errors = 0
    scored_total = scored_agree = 0
    cats: dict[str, list[int]] = {}     # category -> [matches, scored items]
    rows = []
    for it in items:
        r = results[it["id"]]
        gold_v = it["verdict"]
        cat_name = "calib" if it.get("calibration") \
            else it.get("category", "?")
        if r["error"]:
            errors += 1
            if not it.get("calibration"):
                cats.setdefault(it.get("category", "?"), [0, 0])[1] += 1
            rows.append((it["id"], cat_name, gold_v, "ERROR", "",
                         r["error"]))
            continue
        is_scored = not it.get("calibration")
        match = r["verdict"] == gold_v
        if is_scored:
            scored_total += 1
            scored_agree += int(match)
            c = cats.setdefault(it.get("category", "?"), [0, 0])
            c[1] += 1
            c[0] += int(match)
        note = "" if match else \
            ("failed: " + ", ".join(r["failed_checks"])
             if r["verdict"] == "reject" else "graded accept")
        rows.append((it["id"], cat_name, gold_v, r["verdict"],
                     "yes" if match else "NO", note))

    wid = max(len(r[0]) for r in rows)
    cwid = max([len("category")] + [len(r[1]) for r in rows])
    print(f"\n{'item'.ljust(wid)}  {'category'.ljust(cwid)}  gold    "
          "verdict  agree  note")
    for item_id, c, g, v, m, note in rows:
        print(f"{item_id.ljust(wid)}  {c.ljust(cwid)}  {g:7} {v:8} "
              f"{m:6} {note}")

    bar = gold.get("pass_bar")
    full_scored = sum(1 for it in gold["items"] if not it.get("calibration"))
    partial = scored_total != full_scored
    if partial:
        bar = None                      # partial run; the bar reads 20 items
    if cats:
        print("\ncategories: " + "  ".join(
            f"{k} {m}/{t}" for k, (m, t) in sorted(cats.items())))
        print(f"agreement: {scored_agree}/{scored_total} scored items",
              end="")
    else:
        print(f"\nagreement: {scored_agree}/{scored_total} scored items",
              end="")
    if bar is not None:
        floor_missing = sorted(k for k, (m, _) in cats.items() if m == 0)
        # The bar is 18/20 AND the category floor: at least one matching
        # verdict in every composition category (grading tab).
        if floor_missing:
            print(f"  (bar: {bar}/{scored_total}: below the bar; category "
                  f"floor unmet: no match in {', '.join(floor_missing)})")
        elif scored_agree >= bar:
            print(f"  (bar: {bar}/{scored_total}: PASS)")
        else:
            print(f"  (bar: {bar}/{scored_total}: below the bar)")
    else:
        print()
        if partial and scored_total:
            print("partial run: the bar and the category floor are decided "
                  "only by a full run. A loosened check can flip a package "
                  "that agreed before; before the confirming full run, add "
                  "canaries to --only: one already-agreeing package from "
                  "each small category your change could touch (the table's "
                  "category column names each package's category).")
        elif partial:
            print("calibration packages are never scored; their agreement "
                  "is per item in the table above. The bar and the "
                  "category floor are decided only by a full run.")
    if errors:
        print(f"{errors} item(s) errored; fix and re-run.", file=sys.stderr)

    if a.out:
        Path(a.out).write_text(json.dumps({
            "tool_dir": str(tool_dir), "model": MODEL,
            "agreement": [scored_agree, scored_total],
            "results": [dict(results[it["id"]], gold=it["verdict"],
                             category=it.get("category"),
                             calibration=bool(it.get("calibration")))
                        for it in items]}, indent=2),
            encoding="utf-8")
        print(f"full results written to {a.out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
