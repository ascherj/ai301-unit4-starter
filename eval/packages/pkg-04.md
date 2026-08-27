# Eval package: pkg-04

- source: sharkdp/bat#3833
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: sharkdp/bat (60209 stars, archived: no)
- description: A cat(1) clone with wings.
- latest release: v0.26.1 (2025-12-02)
- pull requests: no PR template; standard contribution guide asks for tests with behavior changes and a CHANGELOG.md entry
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### pwsh: paging mode colors don't work (#3833)

opened by stderr-to-devnull (NONE) on 2026-07-08, state open, labels: bug

Latest winget package, in paging mode colors don't work. I use
https://github.com/jftuga/less-Windows

Built-in pager also same issue.

## Thread highlights (0 comments total)

(no comments)

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): on Windows 11 PowerShell
with less-Windows 668 on PATH, `bat --color=always Cargo.toml` prints
colored output, while plain `bat Cargo.toml` (paging auto) pages
through less with raw `ESC[38;5;...m` sequences shown as literal text;
`bat --pager="less -R" Cargo.toml` pages WITH colors. The control
isolates the flag set bat hands the pager: color works exactly when
`-R` reaches less.

Plan: on Windows, `bat` launches a `less` found on PATH without the
`--RAW-CONTROL-CHARS` flag family when it cannot parse the build's
`less --version` banner (less-Windows formats it differently), and
the fallback flag set omits `-R`. Scope, one bounded change: in
`src/pager.rs`, when the version probe fails on Windows, treat the
pager as a modern less and include `-R` in the default flag set,
instead of falling back to the bare invocation. Not in scope: the
built-in pager path or non-Windows behavior. Files: `src/pager.rs`,
one unit test on the flag-set derivation. Test plan: re-run the
repro (`bat Cargo.toml` under pwsh with less-Windows), expect paged
output WITH colors, matching the `--pager="less -R"` control; run the
pager unit tests.

## Candidate PR

### Title

Pass -R to less on Windows when the version probe fails

### Description

Fixes the pwsh paging color issue: when bat cannot parse the version
banner of a less build (less-Windows prints a different format), it
launched less with no flags, so ANSI colors displayed as literal
escape text. The Windows fallback now assumes a modern less and
includes `--RAW-CONTROL-CHARS`, the same flag set the successful
probe path uses. Unit test added for the fallback flag derivation;
CHANGELOG entry included.

### Commits

- 7c02e1d pager: include -R in the Windows fallback flag set
- e1a9b40 changelog: pwsh paging colors

### Diff

```diff
--- a/src/pager.rs
+++ b/src/pager.rs
@@ -142,10 +142,14 @@ impl Pager {
     let parsed_version = parse_less_version(&version_output);
-    let flags = match parsed_version {
-        Some(v) if v >= 530 => vec!["--RAW-CONTROL-CHARS", "--quit-if-one-screen"],
-        Some(_) => vec!["--RAW-CONTROL-CHARS", "--no-init"],
-        None => vec![],
-    };
+    let flags = match parsed_version {
+        Some(v) if v >= 530 => vec!["--RAW-CONTROL-CHARS", "--quit-if-one-screen"],
+        Some(_) => vec!["--RAW-CONTROL-CHARS", "--no-init"],
+        // A less build whose banner we cannot parse (e.g. less-Windows)
+        // is still a less; dropping -R here is what turned colors into
+        // literal escape text on Windows (#3833).
+        None if cfg!(windows) => vec!["--RAW-CONTROL-CHARS"],
+        None => vec![],
+    };
--- a/tests/pager_flags.rs
+++ b/tests/pager_flags.rs
@@ -58,3 +58,12 @@ fn known_less_version_gets_full_flag_set() {
+
+#[test]
+#[cfg(windows)]
+fn unparsable_less_version_still_gets_raw_control_chars() {
+    let flags = derive_flags_for_probe_output("less-Windows custom build");
+    assert!(flags.contains(&"--RAW-CONTROL-CHARS"));
+}
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -4,6 +4,7 @@
 ## Unreleased
 
 ### Bugfixes
+- Pass `-R` to unrecognized `less` builds on Windows, fixing colorless paging under pwsh, see #3833
```

### Test evidence

Tested locally on Windows 11 with less-Windows: colors work now in
paging mode. `cargo test` passes.
