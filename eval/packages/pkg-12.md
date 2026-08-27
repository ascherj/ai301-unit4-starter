# Eval package: pkg-12

- source: sharkdp/bat#3845
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: sharkdp/bat (60209 stars, archived: no)
- description: A cat(1) clone with wings.
- latest release: v0.26.1 (2025-12-02)
- pull requests: no PR template; standard contribution guide asks for tests with behavior changes and a CHANGELOG.md entry
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### bat panics (capacity overflow) on a huge `--line-range` offset-from-end (#3845)

opened by leeewee (CONTRIBUTOR) on 2026-07-17, state open, labels: bug

`bat --line-range :-N` (an offset-from-end range) with a very large
`N` aborts with `capacity overflow` (exit 101). The offset is parsed
as an unbounded `usize` and flows directly into
`VecDeque::with_capacity`, which aborts when the requested capacity
exceeds what the allocator can represent.

```console
$ printf 'l1\nl2\n' | bat --no-config --paging=never --line-range ':-18446744073709551614' -
thread 'main' panicked at src/controller.rs:264:62:
capacity overflow
$ echo $?
101
```

Root cause, `Controller::print_file_ranges` (`src/controller.rs:262-264`):

```rust
// Buffer needs to be 1 greater than the offset to have a look-ahead line for EOF
let buffer_size: usize = line_ranges.largest_offset_from_end() + 1;
let mut buffered_lines: VecDeque<(Vec<u8>, usize)> = VecDeque::with_capacity(buffer_size);
```

`largest_offset_from_end()` returns the raw offset parsed from
`--line-range :-N` with no upper bound. `N == usize::MAX` instead
overflows the `+ 1` (silent wrap in release). Expected: an
out-of-range line offset should be rejected or clamped (bat already
validates other numeric args), not turned into an allocation request
that aborts the process.

## Thread highlights (1 comment total)

- 2026-07-27 vigneshakaviki (NONE): claims a fix in a linked PR.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's command
re-run on 0.26.1 aborts with `capacity overflow`, exit 101; a
control with `:-4` prints the last lines normally; `:-N` with
`N == usize::MAX` confirms the `+ 1` wrap under overflow-checks.

Plan: cap the look-back allocation instead of trusting the parsed
offset. Scope, one bounded change: in
`Controller::print_file_ranges`, compute
`buffer_size = largest_offset_from_end().saturating_add(1)` and
allocate with a lazily-grown `VecDeque::new()` when the requested
capacity exceeds a sane preallocation cap (the deque still grows to
whatever the file actually needs). Not in scope: rejecting large
offsets at parse time or changing `--line-range` semantics. Files:
`src/controller.rs`, one integration test. Test plan: re-run the
repro, expect the last lines printed and exit 0; `:-4` control
unchanged; `cargo test`.

## Candidate PR

### Title

Avoid capacity-overflow abort on huge --line-range offsets from end

### Description

Fixes the `:-N` abort from #3845 per the posted plan: the look-back
buffer now saturates the `+ 1` and only preallocates up to a cap,
letting the deque grow organically for absurd offsets instead of
aborting inside the allocator. Repro and control evidence below;
regression test and CHANGELOG entry included.

### Commits

- 90ff5b2 wip
- e77a20c fix
- 1acd3d9 fmt + cleanup

### Diff

```diff
--- a/src/controller.rs
+++ b/src/controller.rs
@@ -12,7 +12,7 @@ use crate::{
-use std::collections::VecDeque;
+use std::collections::VecDeque; // TODO: ring buffer?
@@ -255,18 +255,33 @@ impl Controller<'_> {
-        // Buffer needs to be 1 greater than the offset to have a look-ahead line for EOF
-        let buffer_size: usize = line_ranges.largest_offset_from_end() + 1;
-        let mut buffered_lines: VecDeque<(Vec<u8>, usize)> = VecDeque::with_capacity(buffer_size);
+        // Buffer needs to be 1 greater than the offset to have a look-ahead line for EOF
+        let buffer_size: usize = line_ranges.largest_offset_from_end().saturating_add(1);
+        // eprintln!("DBG buffer_size = {}", buffer_size);
+        const MAX_PREALLOC: usize = 1 << 20;
+        let mut buffered_lines: VecDeque<(Vec<u8>, usize)> =
+            if buffer_size > MAX_PREALLOC {
+                VecDeque::new()
+            } else {
+                VecDeque::with_capacity(buffer_size)
+            };
+        // let mut buffered_lines: VecDeque<(Vec<u8>, usize)> =
+        //     VecDeque::with_capacity(buffer_size.min(MAX_PREALLOC));
+        // ^ first attempt: min() still preallocates 8MB for the tuple
+        //   headers; keeping for reference
+        fn _unused_buffer_probe(cap: usize) -> usize {
+            // was used to bisect the abort threshold on this machine
+            cap.next_power_of_two()
+        }
@@ -289,11 +304,11 @@ impl Controller<'_> {
-        while reader.read_line(&mut line_buffer)? {
-            let line = std::mem::take(&mut line_buffer);
-            buffered_lines.push_back((line, line_number));
-            if buffered_lines.len() > buffer_size {
-                if let Some((line, number)) = buffered_lines.pop_front() {
-                    self.print_line(&line, number)?;
-                }
-            }
-            line_number += 1;
-        }
+        while reader.read_line(&mut line_buffer)? {
+            let line = std::mem::take(&mut line_buffer);
+            buffered_lines.push_back((line, line_number));
+            if buffered_lines.len() > buffer_size {
+                if let Some((line, number)) = buffered_lines.pop_front() {
+                    self.print_line(&line, number)?;
+                }
+            }
+            line_number += 1;
+        }
--- a/tests/integration_tests.rs
+++ b/tests/integration_tests.rs
@@ -1502,3 +1502,13 @@ fn line_range_from_end() {
+
+#[test]
+fn line_range_huge_offset_from_end_does_not_abort() {
+    // #3845
+    bat()
+        .arg("--line-range=:-18446744073709551614")
+        .write_stdin("l1\nl2\n")
+        .assert()
+        .success()
+        .stdout("l1\nl2\n");
+}
```

### Test evidence

Repro re-run on the branch:

```
$ printf 'l1\nl2\n' | bat --no-config --paging=never --line-range ':-18446744073709551614' -
l1
l2
$ echo $?
0
```

Expected-after per the plan: both lines printed, exit 0 (before:
capacity overflow abort, exit 101). `:-4` control unchanged.
`cargo test` passes (integration suite includes the new regression
test).
