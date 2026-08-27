# Eval package: pkg-01

- source: pandas-dev/pandas#66657
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: pandas-dev/pandas (49517 stars, archived: no)
- description: Flexible and powerful data analysis / manipulation library for Python, providing labeled data structures similar to R data.frame objects, statistical functions, and much more.
- latest release: v3.0.5 (2026-07-22)
- pull requests: the PR template is a required checklist: closes #xxxx with the issue number, tests added and passed, all code checks passed (pre-commit), type annotations added to new arguments, and an entry in the latest doc/source/whatsnew/vX.X.X.rst when fixing a bug
- contribution policy (contributing guide): standard contribution guide with a documented development workflow; no stated AI policy

## Issue

### BUG: read_csv (c engine) heap buffer overflow on short rows before a wide field (#66657)

opened by SABITHSAHEB (NONE) on 2026-08-08, state open, labels: Bug, IO CSV, Segfault

With the C engine, `read_csv` reserves the token stream once per read
buffer for the worst case that the whole buffer is copied 1:1, and the
bulk-copy fast paths in `tokenize_bytes` then write field bytes with no
per-copy capacity check. When a row has fewer fields than expected,
`end_line` closes the missing fields by writing a NUL terminator for
each one. Those synthetic terminators take stream space but consume no
input, so a run of short rows eats into the reservation the bulk copies
rely on; it is restored only for the terminators themselves, not for
the input still waiting to be copied.

Repro (41 rows, 5000 expected columns, then one 100,000-char field):

```python
import io
import pandas as pd

n_cols = 5000
wide = "X" * 100_000
data = "a\n" * 40 + wide + "\n"

df = pd.read_csv(io.StringIO(data), header=None,
                 names=[f"c{i}" for i in range(n_cols)])
print(df.shape)              # (41, 5000) as expected
print(len(df.iloc[40, 0]))   # 99999, but the field is 100000 chars
```

Building with ASAN reports a heap-buffer-overflow WRITE in
`tokenize_bytes`; in a normal build the last field silently loses its
final byte (or corrupts the heap).

## Thread highlights (1 comment total)

- 2026-08-09 DresdenGman (NONE): strong, concrete parser bug: small repro, clear failure mode, actionable ASAN signal. Suggests isolating the stream-space reservation path around `tokenize_bytes` / `end_line` and checking whether short-row padding needs to reserve input-carrying space.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's script re-run
on main under ASAN shows `heap-buffer-overflow WRITE` at the stream
copy in `tokenize_bytes`; without short rows before the wide field
(`data = wide + "\n"`), the same wide field parses cleanly, isolating
the short-row padding as the trigger.

Plan: the reservation drift is in `end_line`'s missing-field padding:
`make_stream_space(ex_fields - fields)` accounts for the synthetic
terminators but not for the input bytes still pending in the buffer.
Scope, one bounded change: in
`pandas/_libs/src/parser/tokenizer.c`, make the bulk-copy paths in
`tokenize_bytes` check remaining stream capacity before copying and
call `make_stream_space` for the pending copy length when short-row
padding has consumed the reservation. Not in scope: restructuring the
one-reservation-per-buffer design or the SIMD fast paths themselves.
Files: `pandas/_libs/src/parser/tokenizer.c`, one regression test in
`pandas/tests/io/parser/test_c_parser_only.py`. Test plan: re-run the
issue's script, expect `len(df.iloc[40, 0]) == 100000` and a clean
ASAN run; run the parser test suite.

## Candidate PR

### Title

Fix read_csv C engine heap overflow on short rows before a wide field

### Description

The C tokenizer under-reserves stream space when short rows pad
missing fields, and a following wide field then writes past the
reservation. This adds a capacity check to the bulk-copy path so the
stream is regrown for the pending copy when padding has consumed the
reservation. A regression test pins the short-rows-then-wide-field
shape; test evidence below.

### Commits

- 41c9f27 parser: reserve stream space for pending copy after short-row padding
- 88d20ab test: regression case for short rows before a wide field

### Diff

```diff
--- a/pandas/_libs/src/parser/tokenizer.c
+++ b/pandas/_libs/src/parser/tokenizer.c
@@ -1096,6 +1096,15 @@ static int tokenize_bytes(parser_t *self,
     char *stream;
     char *buf = self->data + self->datapos;
 
+    // Short rows pad missing fields with synthetic NUL terminators;
+    // make_stream_space() restores space for the terminators only,
+    // not for input still waiting to be copied, so the 1:1 buffer
+    // reservation no longer covers the remaining copy. Regrow here.
+    int64_t pending = self->datalen - self->datapos;
+    if (self->stream_len + pending >= self->stream_cap &&
+        make_stream_space(self, (size_t)pending) < 0) {
+        int64_t bufsize = 100;
+        self->error_msg = malloc(bufsize);
+        snprintf(self->error_msg, bufsize, "out of memory");
+        return -1;
+    }
     if (make_stream_space(self, self->datalen - self->datapos) < 0) {
         int64_t bufsize = 100;
         self->error_msg = malloc(bufsize);
--- a/pandas/tests/io/parser/test_c_parser_only.py
+++ b/pandas/tests/io/parser/test_c_parser_only.py
@@ -733,3 +733,17 @@ def test_bytes_exceed_2gb(c_parser_only):
+
+
+def test_short_rows_before_wide_field(c_parser_only):
+    # GH 66657: short-row padding consumed the stream reservation and
+    # a following wide field overflowed the token stream.
+    parser = c_parser_only
+    wide = "X" * 100_000
+    data = "a\n" * 40 + wide + "\n"
+    result = parser.read_csv(
+        StringIO(data), header=None, names=[f"c{i}" for i in range(5000)]
+    )
+    assert result.shape == (41, 5000)
+    assert len(result.iloc[40, 0]) == 100_000
```

### Test evidence

Issue repro re-run on the branch:

```
$ python repro_66657.py           # before (main): len == 99999
(41, 5000)
99999
$ python repro_66657.py           # after (branch)
(41, 5000)
100000
```

ASAN build: `main` reports heap-buffer-overflow WRITE in
tokenize_bytes on the repro; the branch build runs the same script
with no ASAN report. Parser suite:
`pytest pandas/tests/io/parser -q` passes (2841 passed, 40 skipped),
including the new regression test.
