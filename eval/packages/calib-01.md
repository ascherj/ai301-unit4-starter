# Eval package: calib-01

- source: dandavison/delta#2211
- captured: 2026-08-18
- calibration: true

## Repo facts (captured 2026-08-18)

- repo: dandavison/delta (31792 stars, archived: no)
- description: A syntax-highlighting pager for git, diff, grep, rg --json, and blame output.
- latest release: 0.19.2 (2026-03-28)
- pull requests: no PR template; the contribution docs ask that PRs stay small and reference the issue
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### Duplicate "file-decoration-style" field in "gruvmax-fang" theme config (#2211)

opened by senges (NONE) on 2026-08-10, state open, labels: none

In `themes.gitconfig`, theme "gruvmax-fang" has a duplicate key
`file-decoration-style`:

```
[delta "gruvmax-fang"]
    file-decoration-style = "#434C5E" ul
    file-decoration-style = "#84786A" ul
```

Found while parsing the file with python `configparser`, which
reports a duplicate-key error.

## Thread highlights (0 comments total)

(no comments)

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): `configparser` raises
`DuplicateOptionError: option 'file-decoration-style' in section
'delta "gruvmax-fang"' already exists` on `themes.gitconfig`;
`git config --file themes.gitconfig --get-all
delta.gruvmax-fang.file-decoration-style` prints both values,
confirming the second (`#84786A`) is the one git-config semantics
actually apply.

Plan: two steps. Remove the first, shadowed
`file-decoration-style` line (git-config last-wins means `#84786A`
is the effective value today, so deleting the `#434C5E` line changes
nothing visually), then verify the file parses cleanly with a strict
parser. Not in scope: any other theme. Files: `themes.gitconfig`.
Test plan: re-run the configparser repro, expect a clean parse;
`delta --show-syntax-themes` smoke check that gruvmax-fang still
renders with the `#84786A` decoration.

## Candidate PR

### Title

Remove duplicate file-decoration-style from gruvmax-fang theme

### Description

Removes the shadowed first `file-decoration-style` line from the
gruvmax-fang theme (#2211). Git-config last-wins semantics mean
`#84786A` was already the effective value, so rendering is
unchanged; strict parsers no longer error on the duplicate.

### Commits

- b52ce1a themes: remove shadowed file-decoration-style from gruvmax-fang

### Diff

```diff
--- a/themes.gitconfig
+++ b/themes.gitconfig
@@ -214,7 +214,6 @@
 [delta "gruvmax-fang"]
     ; Powerline blocks: https://gist.github.com/XVilka/8346728
-    file-decoration-style = "#434C5E" ul
     file-decoration-style = "#84786A" ul
     file-style = "#84786A"
     hunk-header-decoration-style = ul
```

### Test evidence

Repro re-run on the branch:

```
$ python3 -c "import configparser; c=configparser.ConfigParser(strict=True); c.read('themes.gitconfig'); print('parsed OK')"
# before: configparser.DuplicateOptionError: ... 'file-decoration-style' ... already exists
# after:
parsed OK
```

`git config --file themes.gitconfig --get-all
delta.gruvmax-fang.file-decoration-style` now prints exactly one
value (`#84786A ul`), the same effective value as before.
`delta --show-syntax-themes | head` renders gruvmax-fang unchanged.
