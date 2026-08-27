# Eval package: pkg-08

- source: jesseduffield/lazygit#5883
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: jesseduffield/lazygit (81448 stars, archived: no)
- description: simple terminal UI for git commands.
- latest release: v0.64.1 (2026-08-12)
- pull requests: template asks for a PR Description and a requirements checklist: cheatsheets up to date (go generate), code formatted, tests added or updated (integration test guide linked), text internationalised, new UserConfig entries hot-reloadable and documented
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### [UX] Pressing 's' to stash untracked files accepts a name but silently does nothing (#5883)

opened by ThatOn3Gu7 (NONE) on 2026-07-31, state open, labels: bug

With an untracked file focused in the Files panel, pressing `s`
(stash) opens the "Stash name" popup as if everything is good to go.
After typing a name and hitting Enter, the popup closes and nothing
happens: the file remains untracked, no stash is created, and no
toast or error explains why. Standard `git stash` ignores untracked
files by default, so the failure makes sense under the hood, but the
name prompt appearing makes the silent failure confusing
(`Shift+S`, stash-including-untracked, is what actually works).

Steps: create an untracked file in a repo with no other changes,
press `s` in the Files panel, type a name, press Enter. The prompt
disappears; nothing is stashed; no notification.

Ideas from the report: an error toast pointing at `Shift+S`, a
fallback prompt to include untracked files, or suppressing the name
prompt when nothing can be stashed.

## Thread highlights (2 comments total)

- 2026-07-31 ThatOn3Gu7 (NONE): hopes for a fix soon.
- 2026-08-08 bhallashivam1997 (NONE): says they pushed a fix for the bug.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): repo with a single
untracked file; `s`, a name, Enter: popup closes, `git stash list`
empty, no toast (screen capture in the report); control with one
tracked modification: same flow creates the stash, isolating
untracked-only state as the trigger.

Plan: the stash handler runs `git stash push` without
`--include-untracked` and discards its "No local changes to save"
outcome, so untracked-only state fails after the prompt with no
signal. Scope, one bounded change, the report's first idea (smallest
surface): before opening the name prompt in the files controller,
check whether any tracked change exists; when only untracked files
are present, show an error toast naming `Shift+S` instead of opening
the prompt. Not in scope: changing stash semantics or adding a
fallback prompt flow. Files:
`pkg/gui/controllers/files_controller.go`, the i18n english set, one
integration test. Test plan: re-run the repro, expect the toast
(with the untracked file still present) and no name prompt; control
with a tracked change still stashes; run the integration test.

## Candidate PR

### Title

Show an error instead of the stash prompt when only untracked files exist

### Description

PR Description: pressing `s` with only untracked files opened a
stash-name prompt whose stash silently failed (#5883, plan posted on
the thread). The files controller now checks for stashable tracked
changes first and shows an error toast pointing at the
stash-include-untracked binding, so the dead-end prompt never opens.

Requirements: cheatsheets regenerated (no binding changes, no diff);
code formatted; integration test added; new error text
internationalised; no UserConfig changes.

### Commits

- 8e02c1a files: error toast instead of stash prompt when nothing is stashable
- 1f9d4b7 i18n: add CannotStashUntrackedOnly text + integration test

### Diff

```diff
--- a/pkg/gui/controllers/files_controller.go
+++ b/pkg/gui/controllers/files_controller.go
@@ -612,6 +612,13 @@ func (self *FilesController) handleStashChanges() error {
 func (self *FilesController) stash() error {
+    // `git stash push` without --include-untracked has nothing to do
+    // when only untracked files exist; the prompt would accept a name
+    // and silently do nothing (#5883). Fail loudly before prompting.
+    if !self.c.Model().AnyTrackedChanges() {
+        return self.c.ErrorMsg(self.c.Tr.CannotStashUntrackedOnly)
+    }
     return self.c.Prompt(types.PromptOpts{
         Title: self.c.Tr.StashChanges,
--- a/pkg/i18n/english.go
+++ b/pkg/i18n/english.go
@@ -1481,6 +1481,7 @@ type TranslationSet struct {
     StashChanges string
+    CannotStashUntrackedOnly string
@@ -2214,6 +2215,7 @@ func EnglishTranslationSet() *TranslationSet {
         StashChanges: "Stash changes",
+        CannotStashUntrackedOnly: "No tracked changes to stash. To stash untracked files, use stash-include-untracked (default: 'S').",
--- a/pkg/integration/tests/stash/stash_untracked_only_errors.go
+++ b/pkg/integration/tests/stash/stash_untracked_only_errors.go
@@ -0,0 +1,20 @@
+var StashUntrackedOnlyErrors = NewIntegrationTest(NewIntegrationTestArgs{
+    Description:  "Pressing stash with only untracked files shows an error instead of a dead prompt",
+    SetupRepo: func(shell *Shell) {
+        shell.CreateFile("untracked.txt", "hello")
+    },
+    Run: func(t *TestDriver, keys config.KeybindingConfig) {
+        t.Views().Files().
+            Focus().
+            Press(keys.Files.StashAllChanges) // the plain 's' stash
+        t.ExpectToast(Contains("No tracked changes to stash"))
+        t.Views().Files().Lines(Contains("untracked.txt"))
+    },
+})
```

### Test evidence

Repro re-run on the branch:

```
before: s -> "Stash name" prompt -> Enter -> nothing (stash list empty)
after:  s -> toast "No tracked changes to stash. To stash untracked
        files, use stash-include-untracked (default: 'S')." -> no
        prompt; untracked.txt still listed
```

Expected-after per the plan: the toast instead of the prompt, file
untouched. Control: with a tracked modification staged, `s` still
prompts and creates the stash. Integration test
`stash_untracked_only_errors` passes; `go test ./...` passes;
`go generate ./...` produces no cheatsheet diff.
