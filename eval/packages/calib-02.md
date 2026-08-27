# Eval package: calib-02

- source: jesseduffield/lazygit#5920
- captured: 2026-08-18
- calibration: true

## Repo facts (captured 2026-08-18)

- repo: jesseduffield/lazygit (81448 stars, archived: no)
- description: simple terminal UI for git commands.
- latest release: v0.64.1 (2026-08-12)
- pull requests: template asks for a PR Description and a requirements checklist: cheatsheets up to date (go generate), code formatted, tests added or updated (integration test guide linked), text internationalised, new UserConfig entries hot-reloadable and documented
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### Accent composition using modified dead keys not working properly on Windows (#5920)

opened by Novaccian (NONE) on 2026-08-12, state open, labels: bug

For languages that use diacritics, a common way to type them is to
press and release a "dead key" representing the accent, then the
base character. To type `é` on the "Romanian (Programmers)" layout,
the reporter types `AltGr-9 e`; in lazygit this results in `9é`,
forcing them to go back and delete the `9`.

Steps: set the layout to Romanian (Programmers); edit a commit
message in lazygit; type an accented character using AltGr plus 3, 7,
or 9. The dead key is inserted on its own, then the accented letter
follows. Expected: dead keys are not inserted on their own.
Non-modified dead keys (United States-International layout, `' e`)
work as expected. Reproduced in cmd.exe and Windows Terminal; both
terminals work correctly outside lazygit with the same layout.

## Thread highlights (0 comments total)

(no comments)

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): on Windows 11 with the
Romanian (Programmers) layout, `AltGr-9 e` in lazygit's commit
editor inserts `9é` (screen capture); the same sequence in
PowerShell at the same terminal inserts `é` alone, isolating
lazygit's input handling rather than the terminal.

Plan: lazygit's Windows input path receives the AltGr-modified dead
key as a keypress with the ctrl+alt modifier set and inserts its
base character instead of waiting for the composition to resolve.
Scope, one bounded change: in the gocui event translation for
Windows, when a key event carries the AltGr modifier pattern AND
maps to a dead key in the active layout (the console reports it with
the dead-key unicode flag), suppress the immediate insertion and let
the next character event deliver the composed result. Not in scope:
non-Windows input, IME composition, or key binding changes. Files:
the vendored gocui Windows input translation and one unit test with
a recorded event sequence. Test plan: re-run the repro (AltGr-9
then e), expect `é` alone; the US-International control (`' e`)
unchanged; go test on the touched package.

## Candidate PR

### Title

fixed the dead keys bug!!

### Description

typing accents on windows was broken for me too so i had claude look
at it and this should fix it. i bumped the terminal library to
latest since the changelog mentioned keyboard fixes and cleaned up
some formatting while i was in there. did not get a chance to test
on an actual romanian layout but the library update looks right.

### Commits

- 09fcf12 fixed dead keys (hopefully)
- 4b0a3d7 bump tcell
- c11d9e0 gofmt

### Diff

```diff
--- a/go.mod
+++ b/go.mod
@@ -14,7 +14,7 @@ require (
 	github.com/gdamore/encoding v1.0.0 // indirect
-	github.com/gdamore/tcell/v2 v2.7.4
+	github.com/gdamore/tcell/v2 v2.9.0
 	github.com/go-errors/errors v1.5.1
--- a/go.sum
+++ b/go.sum
@@ -44,8 +44,8 @@ github.com/gdamore/encoding v1.0.0/go.mod h1:alR0ol34c49FCSBLjhosxzcPHQbf2trDkoo5
-github.com/gdamore/tcell/v2 v2.7.4 h1:sg6/UnTM9jGpZU+oFYAsDahfchWAFW8Xx2yFinNSAYU=
-github.com/gdamore/tcell/v2 v2.7.4/go.mod h1:dSXtXTSK0VsW1biw65DZLZ2NKr7j0qP/0J7ONmsraWg=
+github.com/gdamore/tcell/v2 v2.9.0 h1:xLTzOwqtUqe8JuNyLu5tmvZNJdBJmYDWWLOykafgwlE=
+github.com/gdamore/tcell/v2 v2.9.0/go.mod h1:2Jc4dNKQ5FYtLmm2CdV3ppwkNQ4cBSgAyGONE6NPIhU=
--- a/pkg/gui/gui.go
+++ b/pkg/gui/gui.go
@@ -388,9 +388,7 @@ func (gui *Gui) createAllViews() error {
-	commitMessageView.Editable = true
-	commitMessageView.Editor = gocui.EditorFunc(commitMessageEditor)
-	commitMessageView.Visible = false
+	commitMessageView.Editable, commitMessageView.Visible = true, false
+	commitMessageView.Editor = gocui.EditorFunc(commitMessageEditor)
@@ -412,8 +410,7 @@ func (gui *Gui) createAllViews() error {
-	confirmationView.Visible = false
-	confirmationView.Editable = true
+	confirmationView.Visible, confirmationView.Editable = false, true
```

### Test evidence

(none provided)
