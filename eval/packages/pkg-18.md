# Eval package: pkg-18

- source: nushell/nushell#18850
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: nushell/nushell (40293 stars, archived: no)
- description: A new type of shell.
- latest release: 0.115.0 (2026-08-15)
- pull requests: template asks for a Description section (problem, approach, technical details) and a User-facing changes section used to generate release notes; the contributing guide is linked from the template
- contribution policy (CONTRIBUTING.md): standard contribution guide with formatting and test commands (cargo fmt, clippy, cargo test); no stated AI policy

## Issue

### `nu --help` prints ansi escape sequence even when stdout is not tty (#18850)

opened by jcornaz (NONE) on 2026-08-17, state open, labels: status:needs-triage

Running `nu --help | less` shows raw escape sequences
(`ESC[32mGeneral:ESC[0m`, `ESC[36m-hESC[0m`, and so on) through the
whole help text: the help printer colors its output unconditionally,
without checking whether stdout is a terminal.

## Thread highlights (8 comments total)

- 2026-08-17 cptpiepmatz (MEMBER): asks what `config use-colors | less` returns, hoping false.
- 2026-08-17 jcornaz (NONE): it returns a blank page.
- 2026-08-17 fdncred (CONTRIBUTOR): `$env.LESS = "-FRXS"` makes the less commands work fine.
- 2026-08-17 jcornaz (NONE): `less -r` is a workaround for the repro step, but the underlying issue stands: `nu --help` prints escape codes when stdout is not a tty.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): `nu --help | cat -v`
shows `^[[32m` sequences on 0.115.0; the control `nu --help` on a
terminal renders colored help, and `nu ls | cat -v` shows table
output already degrades to plain text when piped, so the help
printer is the one path skipping the tty check.

Plan: the `--help` banner printer colors sections and flags
unconditionally. Scope, one bounded change: in the main help
printing path (`src/command.rs`), gate the color styling on stdout
being a terminal (the same `std::io::IsTerminal` check the table
printer uses), falling back to plain text when piped or redirected.
Not in scope: honoring `config use-colors` for `--help` (config is
not loaded that early; noted in the plan as a possible follow-up) or
any other command's output. Files: `src/command.rs`, one test.
Test plan: re-run `nu --help | cat -v`, expect no escape sequences;
`nu --help` on a tty still colored; cargo test.

## Candidate PR

### Title

Print plain --help when stdout is not a terminal

### Description

Description: `nu --help | less` showed raw ANSI sequences because
the help printer styles unconditionally (#18850). The styling is now
gated on `std::io::stdout().is_terminal()`, matching how table
output already degrades when piped. Per the plan, `config
use-colors` stays out of scope for `--help` (config is not loaded at
that point).

User-facing changes: `nu --help` piped or redirected now prints
plain text.

### Commits

- 0e6b1a2 gate --help colors on stdout being a terminal
- 9c37d51 fmt pass on command.rs

### Diff

```diff
--- a/src/command.rs
+++ b/src/command.rs
@@ -1,10 +1,11 @@
-use nu_engine::{command_prelude::*, get_full_help};
-use nu_protocol::{
-    ast::{Expr, Expression},
-    engine::{EngineState, Stack, StateWorkingSet},
-    Category, ShellError, Signature, Spanned, SyntaxShape, Value,
-};
+use nu_engine::command_prelude::*;
+use nu_engine::get_full_help;
+use nu_protocol::ast::{Expr, Expression};
+use nu_protocol::engine::{EngineState, Stack, StateWorkingSet};
+use nu_protocol::{Category, ShellError, Signature, Spanned, SyntaxShape, Value};
+use std::io::IsTerminal;
@@ -214,20 +215,24 @@ fn print_help_banner(engine_state: &EngineState) {
-    let g = "\x1b[32m";
-    let c = "\x1b[36m";
-    let d = "\x1b[2;39m";
-    let r = "\x1b[0m";
+    // eprintln!("help colors: tty={}", std::io::stdout().is_terminal());
+    let colorize = std::io::stdout().is_terminal();
+    let (g, c, d, r) = if colorize {
+        ("\x1b[32m", "\x1b[36m", "\x1b[2;39m", "\x1b[0m")
+    } else {
+        ("", "", "", "")
+    };
 
-    println!("{g}General:{r}");
-    println!("  {c}-h{r}, {c}--help{r}");
-    println!("      {d}show this help message{r}");
+    println!("{g}General:{r}");
+    println!("  {c}-h{r}, {c}--help{r}");
+    println!("      {d}show this help message{r}");
@@ -246,14 +251,14 @@ fn print_help_banner(engine_state: &EngineState) {
-    println!("{g}Startup:{r}");
-    println!("  {c}-i{r}, {c}--interactive{r}");
-    println!("      {d}start as an interactive shell{r}");
-    println!("  {c}-l{r}, {c}--login{r}");
-    println!("      {d}start as a login shell{r}");
-    println!("  {c}-c{r}, {c}--commands{r} <{d}string{r}>");
-    println!("      {d}run the given commands and then exit{r}");
+    println!("{g}Startup:{r}");
+    println!("  {c}-i{r}, {c}--interactive{r}");
+    println!("      {d}start as an interactive shell{r}");
+    println!("  {c}-l{r}, {c}--login{r}");
+    println!("      {d}start as a login shell{r}");
+    println!("  {c}-c{r}, {c}--commands{r} <{d}string{r}>");
+    println!("      {d}run the given commands and then exit{r}");
--- a/tests/main.rs
+++ b/tests/main.rs
@@ -77,3 +77,11 @@ fn help_exits_zero() {
+
+#[test]
+fn help_piped_has_no_ansi_escapes() {
+    // #18850
+    let out = nu_command().arg("--help").pipe_stdout().output();
+    assert!(!String::from_utf8_lossy(&out.stdout).contains('\x1b'));
+}
```

### Test evidence

Repro re-run on the branch:

```
$ nu --help | cat -v | grep -c '\^\['     # before: 214
214
$ ./target/release/nu --help | cat -v | grep -c '\^\['   # after
0
```

On a tty, `nu --help` still renders the colored sections (screenshot
attached). Expected-after per the plan on both counts. `cargo test`
passes; fmt and clippy clean.
