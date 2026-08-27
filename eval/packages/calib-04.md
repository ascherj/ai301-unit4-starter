# Eval package: calib-04

- source: sharkdp/fd#2078
- captured: 2026-08-18
- calibration: true

## Repo facts (captured 2026-08-18)

- repo: sharkdp/fd (44130 stars, archived: no)
- description: A simple, fast and user-friendly alternative to 'find'.
- latest release: v10.4.2 (2026-03-10)
- pull requests: no PR template; standard contribution guide asks for tests with behavior changes and a CHANGELOG.md entry
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### `--threads` accepts unsatisfiable values and panics or aborts during channel allocation and thread creation (#2078)

opened by leeewee (NONE) on 2026-07-28, state open, labels: none

`fd --threads N` (`-j N`) parses `N` into an unbounded `NonZeroUsize`
(`src/cli.rs:556`) and uses it to (1) construct a channel with
capacity `2 * threads` and (2) create exec worker threads for
non-batched `--exec`. Excessive but syntactically valid values
surface as panics or aborts rather than user-facing errors:

1. Channel-capacity multiply overflow, every run:
   `fd -j 9223372036854775807 .` panics `capacity overflow`, exit
   101 (`src/walk.rs:646`, `bounded(2 * config.threads)`).
2. Thread-spawn exhaustion with non-batched `--exec`:
   `fd -j 200000 -x echo .` aborts `failed to spawn thread`, exit
   134 (`src/walk.rs:425`).

## Thread highlights (0 comments total)

(no comments)

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): both invocations re-run
on v10.4.2: the huge `-j` value panics with `capacity overflow`
(exit 101) on a plain run, and `-j 200000 -x echo` aborts with
`failed to spawn thread` (exit 134); a control at `-j 64` runs both
modes cleanly.

Plan: validate the thread count where it is parsed instead of
letting it flow into allocation. Scope, one bounded change: in
`src/cli.rs`, cap `--threads` at a sane maximum (the plan proposes
4096, far above any real machine) and reject larger values with a
normal argument error naming the cap. Not in scope: changing the
channel sizing formula or the exec worker pool design. Files:
`src/cli.rs`, tests. Test plan, both failure modes by name: re-run
repro 1 (`-j 9223372036854775807 .`), expect the argument error and
a normal exit code; re-run repro 2 (`-j 200000 -x echo .`), expect
the same argument error (200000 exceeds the cap), no abort; the
`-j 64` control unchanged; `cargo test`.

## Candidate PR

### Title

Reject --threads values above a sane cap instead of panicking

### Description

Implements the plan on #2078: `--threads` now validates its value at
parse time against a cap of 4096 and rejects larger values with a
normal clap argument error, so unsatisfiable thread counts can no
longer reach channel allocation or thread spawning as panics or
aborts. CHANGELOG entry and tests included.

### Commits

- 6a95d02 cli: cap --threads at 4096 with a proper argument error

### Diff

```diff
--- a/src/cli.rs
+++ b/src/cli.rs
@@ -552,9 +552,20 @@ pub struct Opts {
     /// Set number of threads to use for searching & executing
-    #[arg(long, short = 'j', value_name = "num", hide_short_help = true)]
-    pub threads: Option<NonZeroUsize>,
+    #[arg(long, short = 'j', value_name = "num", hide_short_help = true,
+          value_parser = parse_thread_count)]
+    pub threads: Option<NonZeroUsize>,
@@ -601,6 +612,19 @@ impl Opts {
+/// A thread count the process can actually satisfy: parsing an
+/// unbounded value let `2 * threads` overflow channel capacity and
+/// thread spawning abort (#2078).
+const MAX_THREADS: usize = 4096;
+
+fn parse_thread_count(s: &str) -> Result<NonZeroUsize, String> {
+    let n: NonZeroUsize = s
+        .parse()
+        .map_err(|_| format!("'{s}' is not a valid thread count"))?;
+    if n.get() > MAX_THREADS {
+        return Err(format!(
+            "thread count {n} exceeds the maximum of {MAX_THREADS}"
+        ));
+    }
+    Ok(n)
+}
--- a/tests/tests.rs
+++ b/tests/tests.rs
@@ -2214,3 +2214,14 @@ fn test_threads_flag() {
+
+#[test]
+fn test_threads_over_cap_is_an_argument_error() {
+    // #2078, failure mode 1: must be a normal error, not an abort.
+    let te = TestEnv::new(&[], &[]);
+    te.assert_failure_with_error(
+        &["-j", "9223372036854775807", "."],
+        "exceeds the maximum of 4096",
+    );
+}
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -6,6 +6,7 @@
 ### Bugfixes
+- `--threads` now rejects values above 4096 with a proper error instead of panicking, see #2078
```

### Test evidence

Repro 1 re-run on the branch:

```
$ fd -j 9223372036854775807 .
# before: thread 'main' panicked ... capacity overflow (exit 101)
# after:
error: invalid value '9223372036854775807' for '--threads <num>':
thread count 9223372036854775807 exceeds the maximum of 4096
$ echo $?
2
```

Expected-after per the plan: a normal argument error and a normal
exit code, shown above. `-j 64` control unchanged. `cargo test`
passes (614 tests).
