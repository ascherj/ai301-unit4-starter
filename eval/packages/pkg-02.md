# Eval package: pkg-02

- source: Textualize/rich#4208
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: Textualize/rich (57085 stars, archived: no)
- description: Rich is a Python library for rich text and beautiful formatting in the terminal.
- latest release: v15.0.0 (2026-04-12)
- pull requests: template notes Rich is not accepting new features (bugfixes always welcome; when in doubt open a discussion first) and asks for a type-of-changes checklist and a CHANGELOG.md entry
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### [BUG] Console.save_text clears recorded output when file write fails (#4208)

opened by sanjay3941 (NONE) on 2026-08-16, state open, labels: Needs triage

When using `Console(record=True)`, calling `save_text()` with
`clear=True` (the default) clears the recorded console output even
when the file cannot be written:

```python
from rich.console import Console

console = Console(record=True)
console.print("IMPORTANT OUTPUT")
print(repr(console.export_text()))          # 'IMPORTANT OUTPUT\n'
try:
    console.save_text(r"Z:\no\such\path\output.txt")
except Exception as e:
    print(type(e).__name__, e)              # FileNotFoundError ...
print(repr(console.export_text()))          # '' -- record is gone
```

The file was not successfully written, but the recorded output was
also cleared. Expected: the recorded output remains available when the
save fails, since nothing was persisted.

## Thread highlights (2 comments total)

- 2026-08-17 vardhans07 (NONE): looks like a valid bug; asks to take it up and work on a fix.
- 2026-08-17 vardhans07 (NONE): reports a fix with regression tests for save_text, save_html, and save_svg on a fork branch.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's script re-run
on v15.0.0 shows `export_text()` returning `''` after the failed
`save_text` to a nonexistent path; a control run with a writable path
shows the same clear happening after a successful write, confirming
the clear is unconditional in the export call, not the write.

Plan: `Console.save_text`, `save_html`, and `save_svg` each call their
`export_*` counterpart with `clear=clear` BEFORE opening the file, so
the record is destroyed even when `open()` or `write()` raises. Scope,
one bounded change: in `rich/console.py`, export with `clear=False`,
write the file, and clear the record only after the write succeeds,
in all three `save_*` methods (same one-shape fix, same file). Not in
scope: changing the `clear=True` default or the export API. Files:
`rich/console.py`, `tests/test_console.py`, `CHANGELOG.md` (the
repo's stated entry ask). Test plan: re-run the
issue's script, expect `export_text()` to still return
`'IMPORTANT OUTPUT\n'` after the failed save; a successful save still
clears; run pytest.

## Candidate PR

### Title

Preserve recorded output when Console.save_* fails to write

### Description

Bug fix per the plan on #4208: `save_text`, `save_html`, and
`save_svg` cleared the record inside the export call before touching
the filesystem, so a failed write destroyed the recording. The save
methods now export without clearing, write, and clear only after the
write succeeds. No API or default changes; CHANGELOG.md entry added.

Type of changes: Bug fix.

### Commits

- 3f8a1c2 console: clear recorded output only after save_* writes succeed

### Diff

```diff
--- a/rich/console.py
+++ b/rich/console.py
@@ -2455,9 +2455,12 @@ class Console:
     def save_text(self, path: str, *, clear: bool = True, styles: bool = False) -> None:
-        text = self.export_text(clear=clear, styles=styles)
+        text = self.export_text(clear=False, styles=styles)
         with open(path, "wt", encoding="utf-8") as write_file:
             write_file.write(text)
+        if clear:
+            del self._record_buffer[:]
@@ -2494,9 +2497,12 @@ class Console:
     def save_html(
-        html = self.export_html(
-            theme=theme,
-            clear=clear,
+        html = self.export_html(
+            theme=theme,
+            clear=False,
             code_format=code_format,
             inline_styles=inline_styles,
         )
         with open(path, "wt", encoding="utf-8") as write_file:
             write_file.write(html)
+        if clear:
+            del self._record_buffer[:]
@@ -2543,9 +2549,12 @@ class Console:
     def save_svg(
-        svg = self.export_svg(
-            title=title,
-            theme=theme,
-            clear=clear,
+        svg = self.export_svg(
+            title=title,
+            theme=theme,
+            clear=False,
             code_format=code_format,
         )
         with open(path, "wt", encoding="utf-8") as write_file:
             write_file.write(svg)
+        if clear:
+            del self._record_buffer[:]
--- a/tests/test_console.py
+++ b/tests/test_console.py
@@ -1042,3 +1042,16 @@ def test_save_text():
+
+
+def test_save_text_failed_write_preserves_record(tmp_path):
+    # https://github.com/Textualize/rich/issues/4208
+    console = Console(record=True)
+    console.print("IMPORTANT OUTPUT")
+    missing = tmp_path / "no" / "such" / "dir" / "out.txt"
+    with pytest.raises(OSError):
+        console.save_text(str(missing))
+    assert console.export_text(clear=False) == "IMPORTANT OUTPUT\n"
+    ok = tmp_path / "out.txt"
+    console.save_text(str(ok))
+    assert console.export_text(clear=False) == ""
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,6 +5,10 @@
 ## Unreleased
 
+### Fixed
+
+- `Console.save_text`, `save_html`, and `save_svg` no longer clear the recorded output when the file write fails https://github.com/Textualize/rich/issues/4208
+
```

### Test evidence

Issue repro re-run on the branch:

```
$ python repro_4208.py            # before (v15.0.0)
'IMPORTANT OUTPUT\n'
FileNotFoundError [Errno 2] No such file or directory: 'Z:\\no\\such\\path\\output.txt'
''
$ python repro_4208.py            # after (branch)
'IMPORTANT OUTPUT\n'
FileNotFoundError [Errno 2] No such file or directory: 'Z:\\no\\such\\path\\output.txt'
'IMPORTANT OUTPUT\n'
```

Expected-after per the plan: the record survives the failed save, and
a successful save still clears it (covered by the new test's second
half). `pytest tests/ -q` passes (1462 passed, 12 skipped).
