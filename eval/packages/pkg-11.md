# Eval package: pkg-11

- source: BurntSushi/ripgrep#3477
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: BurntSushi/ripgrep (67388 stars, archived: no)
- description: ripgrep recursively searches directories for a regex pattern while respecting your gitignore.
- latest release: 15.2.0 (2026-07-15)
- pull requests: no PR template; the contribution docs ask for tests with behavior changes and concise, focused PRs
- contribution policy (CONTRIBUTING.md section "Use of AI", AI_POLICY.md): AI-assisted coding is welcome with a human in the loop who understands the work; comments to maintainers must be written by humans in their own words, and AI-generated comments may be hidden

## Issue

### Escaped trailing space in .gitignore causes dangling \ error (differs from git) (#3477)

opened by LordAizen1 (NONE) on 2026-07-17, state open, labels: none

A small mismatch with how git handles escaped trailing spaces in
.gitignore. With `foo\ ` followed by two more spaces in .gitignore
(a backslash-escaped space, then unescaped trailing spaces):

```
$ git check-ignore -v 'foo '
.gitignore:1:foo\       foo
```

Git accepts this and ignores `foo ` correctly. But ripgrep errors:

```
$ rg hi
rg: ./.gitignore: line 1: error parsing glob 'foo\': dangling '\'
```

Git trims normal trailing spaces but keeps the escaped one; ripgrep
trims the escaped space as well, leaving `foo\`, which becomes a
dangling backslash and a parse error. Expected: no parse error, and
the pattern matches `foo ` (like #2236, where a valid but uncommon
pattern caused a dangling `\` error and was fixed).

## Thread highlights (1 comment total)

- 2026-08-18 HarnageaGabriel (NONE): investigating a fix; taking a fresh look at the trailing-whitespace/backslash handling in the gitignore glob parser.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): `.gitignore` written with
`printf 'foo\\   \n'` (verified with `od -c`); `rg hi` errors with
`dangling '\'` while `git check-ignore -v 'foo '` matches; a control
without the trailing unescaped spaces (`foo\ ` exactly) parses fine
in both tools, isolating the trim step as the divergence.

Plan: the gitignore line parser in `crates/ignore/src/gitignore.rs`
strips trailing whitespace without checking whether the last space
is backslash-escaped. Scope, one bounded change: trim trailing
spaces only up to the first escaped space (a space preceded by an
odd number of backslashes stays), matching git's documented
behavior. Not in scope: any other whitespace or escape semantics.
Files: `crates/ignore/src/gitignore.rs`, tests in the same file.
Test plan: re-run the repro, expect no parse error and `foo ` to be
ignored (parity with `git check-ignore`); `cargo test -p ignore`.

## Candidate PR

### Title

ignore: keep backslash-escaped trailing space when trimming gitignore lines

### Description

Trailing-space trimming in the gitignore parser also removed an
escaped trailing space, leaving a dangling backslash and a parse
error where git accepts the pattern (#3477). The trim now stops at a
space preceded by an odd number of backslashes, matching git. One
function touched, tests added for the escaped, unescaped, and
double-backslash cases. Per the repo's AI policy: this change was
AI-assisted with me reviewing and understanding every line, and this
text is in my own words.

### Commits

- 6b93e11 ignore: stop trailing-space trim at escaped spaces

### Diff

```diff
--- a/crates/ignore/src/gitignore.rs
+++ b/crates/ignore/src/gitignore.rs
@@ -518,10 +518,23 @@ fn parse_gitignore_line(line: &str) -> Option<Glob> {
-    // Trailing whitespace is ignored unless it is escaped.
-    let line = line.trim_end_matches(' ');
+    // Trailing whitespace is ignored unless it is escaped: git trims
+    // unescaped trailing spaces but keeps a space preceded by an odd
+    // number of backslashes (gitignore(5)). Trimming past the escape
+    // left a dangling '\' (#3477).
+    let line = trim_unescaped_trailing_spaces(line);
@@ -545,6 +558,20 @@ fn parse_gitignore_line(line: &str) -> Option<Glob> {
+fn trim_unescaped_trailing_spaces(line: &str) -> &str {
+    let bytes = line.as_bytes();
+    let mut end = bytes.len();
+    while end > 0 && bytes[end - 1] == b' ' {
+        let backslashes =
+            bytes[..end - 1].iter().rev().take_while(|&&b| b == b'\\').count();
+        if backslashes % 2 == 1 {
+            break;
+        }
+        end -= 1;
+    }
+    &line[..end]
+}
@@ -1108,3 +1135,15 @@ mod tests {
+    #[test]
+    fn escaped_trailing_space_is_kept() {
+        // #3477: 'foo\ ' plus unescaped trailing spaces must parse and
+        // match "foo " like git does.
+        let gi = gitignore_from_str("foo\\   \n");
+        assert!(gi.matched("foo ", false).is_ignore());
+        assert!(!gi.matched("foo", false).is_ignore());
+        let gi = gitignore_from_str("foo\\\\   \n");
+        assert!(gi.matched("foo\\", false).is_ignore());
+    }
```

### Test evidence

Repro re-run on the branch:

```
$ printf 'foo\\   \n' > .gitignore
$ rg hi                      # before: rg: ./.gitignore: line 1: error
                             # parsing glob 'foo\': dangling '\'
$ rg hi                      # after: searches normally, no error
$ touch 'foo '
$ rg --files                 # after: 'foo ' not listed (ignored),
                             # matching git check-ignore -v 'foo '
```

Expected-after per the plan: no parse error and parity with git on
`foo `. `cargo test -p ignore` passes (214 tests).
