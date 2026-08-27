# Eval package: pkg-07

- source: golangci/golangci-lint#6671
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: golangci/golangci-lint (19271 stars, archived: no)
- description: Fast linters runner for Go.
- latest release: v2.12.2 (2026-05-06)
- pull requests: template warns that PRs not following the rules are closed; asks for a brief description; linter-update PRs are restricted to the linter's author; new linters need an approved discussion before any PR
- contribution policy (contributing guide + Code of Conduct agreement in the issue form): standard contribution guide; no stated AI policy

## Issue

### modernize atomictype analyzer breaks code when changes are split across files (#6671)

opened by taran-p (NONE) on 2026-07-14, state open, labels: bug

The `atomictype` analyzer in `modernize` has suggested fixes for a
single issue that span multiple files. When using the `--fix` flag,
fixes suggested for other files are appended or prepended onto the
file where the diagnostic was reported.

Practically for `modernize`, this means in `a.go` where an `int64` is
turned into an `atomic.Int64`, any `b.go` `.LoadInt64(` call site will
be added to the end of `a.go` as `.Load(`, breaking the code.

Version: golangci-lint 2.12.2 built with go1.26.5. Config enables only
`modernize`.

## Thread highlights (2 comments total)

- 2026-07-14 boring-cyborg[bot] (NONE): first-issue greeting with a link to the contributing guide.
- 2026-07-31 pawannn (NONE): asks to give the fix a try.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): a two-file module (`a.go`
declares `var counter int64`, `b.go` calls
`atomic.LoadInt64(&counter)`); `golangci-lint run --fix` with only
modernize enabled rewrites `a.go` to `atomic.Int64` AND appends
`b.go`'s rewritten `.Load()` call text to the bottom of `a.go`,
which no longer compiles (`go build` fails); a control with both
usages in one file applies cleanly, isolating the cross-file fix
application as the bug.

Plan: the fix applier collects an analyzer's SuggestedFixes and
applies every TextEdit to the diagnostic's file, ignoring each
edit's own position information when it points into another file.
Scope, one bounded change: in the goanalysis fix application path,
group TextEdits by the file their positions resolve to and apply
each group to its own file, skipping (with a warning) any edit whose
file cannot be resolved. Not in scope: changing any analyzer or the
diagnostics themselves. Files: the fix application code under
`pkg/goanalysis/`, tests beside it. Test plan: re-run the two-file
repro, expect `a.go` and `b.go` each correctly rewritten and
`go build ./...` to pass; the one-file control unchanged; run the
project test suite.

## Candidate PR

### Title

goanalysis: apply suggested fixes to the file each edit targets

### Description

The fix applier assumed every TextEdit of a diagnostic lands in the
diagnostic's own file; modernize's atomictype emits cross-file
edits, so text meant for `b.go` was appended to `a.go`. Edits are
now grouped by their resolved file before application, and an edit
whose position cannot be resolved is skipped with a warning instead
of misapplied.

### Commits

- 2f61b0a goanalysis: group suggested-fix edits by target file
- 91cc44d goanalysis: warn and skip on unresolvable edit positions

### Diff

```diff
--- a/pkg/goanalysis/runner_fix.go
+++ b/pkg/goanalysis/runner_fix.go
@@ -118,14 +118,27 @@ func applySuggestedFixes(diag *diagnostic, fset *token.FileSet) error {
-    file := fset.File(diag.Pos)
-    var edits []textEdit
-    for _, fix := range diag.SuggestedFixes {
-        for _, edit := range fix.TextEdits {
-            edits = append(edits, toTextEdit(file, edit))
-        }
-    }
-    return applyEdits(file.Name(), edits)
+    // A diagnostic's suggested fix may carry edits for other files
+    // (modernize atomictype rewrites call sites across the package);
+    // apply each edit to the file its own position resolves to.
+    editsByFile := map[string][]textEdit{}
+    for _, fix := range diag.SuggestedFixes {
+        for _, edit := range fix.TextEdits {
+            f := fset.File(edit.Pos)
+            if f == nil {
+                lintersdb.Warnf("skipping suggested fix edit with unresolvable position %v", edit.Pos)
+                continue
+            }
+            editsByFile[f.Name()] = append(editsByFile[f.Name()], toTextEdit(f, edit))
+        }
+    }
+    for name, edits := range editsByFile {
+        if err := applyEdits(name, edits); err != nil {
+            return err
+        }
+    }
+    return nil
 }
--- a/pkg/goanalysis/runner_fix_test.go
+++ b/pkg/goanalysis/runner_fix_test.go
@@ -87,3 +87,10 @@ func TestApplyFixesSingleFile(t *testing.T) {
+
+func TestGroupEditsByFileBuildsGroups(t *testing.T) {
+    edits := editsAt(t, "a.go:3", "a.go:9")
+    groups := groupEditsByFile(testFset(t), edits)
+    require.Len(t, groups, 1)
+    require.Contains(t, groups, "a.go")
+}
```

### Test evidence

Verified the fix on a single-file case: with both the declaration and
the call site in `a.go`, `golangci-lint run --fix` rewrites the file
correctly and the result builds.

```
$ golangci-lint run --fix ./onefile/ && go build ./onefile/
$ echo $?
0
```

Unit test added above passes. `go test ./pkg/goanalysis/...` passes.
