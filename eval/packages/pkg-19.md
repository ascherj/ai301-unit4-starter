# Eval package: pkg-19

- source: mikefarah/yq#2819
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: mikefarah/yq (15853 stars, archived: no)
- description: yq is a portable command-line YAML, JSON, XML, CSV, TOML, HCL and properties processor.
- latest release: v4.53.4 (2026-08-19)
- pull requests: no PR template; the contribution docs ask for tests with fixes
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### Single-quoted multi-line flow scalar ending with a blank line loses indentation level on output (#2819)

opened by taisph (NONE) on 2026-08-18, state open, labels: bug, v4

Running the YAML below through `yq .` puts the closing single-quote
at the wrong indentation level:

Input (`source.yml`):

```yaml
paths:
  /v1/quack:
    get:
      description: '
        Get quacked.

        - Duck

        '
```

Actual output:

```yaml
paths:
  /v1/quack:
    get:
      description: ' Get quacked.

        - Duck

'
```

Expected: the input preserved. Oddly, yq treats the output as valid
and parsable even though other tools flag it as incorrect;
double-quoting does not exhibit the behavior. yq 4.53.2 and 4.53.3,
Ubuntu Linux.

## Thread highlights (0 comments total)

(no comments)

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's file re-run
through `yq .` on 4.53.3 reproduces the dedented closing quote;
controls show the double-quoted twin round-trips correctly and a
single-quoted scalar WITHOUT the trailing blank line round-trips
correctly, isolating the trailing-line-break handling of the
single-quote emitter.

Plan: in the vendored go-yaml emitter
(`vendor/github.com/mikefarah/yaml/v3/emitterc.go`), the
single-quoted writer resets the emitter's indentation state after
writing a line break; the double-quoted writer preserves it, which
is why the double-quoted twin round-trips. The reset is what writes
the continuation after a trailing blank line, and the closing quote,
without the flow-scalar indent. Scope, one bounded change: in
`yaml_emitter_write_single_quoted_scalar`, stop resetting the
indentation state at the break-writing site, matching the
double-quoted writer's break handling exactly (the trailing-blank-
line dedent from the issue is the visible symptom of that reset).
Not in scope: any other scalar style or the parser. Files: the
emitter file, a round-trip regression test in the yq operator tests.
Test plan: re-run `yq . source.yml`, expect byte-identical
round-trip of the issue's input; the two controls unchanged;
`go test ./...`.

## Candidate PR

### Title

Preserve indent for single-quoted scalars ending in a blank line

### Description

The single-quote emitter reset its indent state after writing a
line break, which dedented the continuation after a trailing blank
line and the closing quote itself (#2819). Per the plan, the reset
is removed from the break-writing site, matching the double-quoted
writer's break handling exactly. Round-trip regression test added
from the issue's input.

### Commits

- e4f7c88 emitter: keep flow indent across trailing breaks in single-quoted scalars

### Diff

```diff
--- a/vendor/github.com/mikefarah/yaml/v3/emitterc.go
+++ b/vendor/github.com/mikefarah/yaml/v3/emitterc.go
@@ -1893,13 +1893,12 @@ func yaml_emitter_write_single_quoted_scalar(emitter *yaml_emitter_t, value []by
 		if is_break(value, i) {
 			if !write_break(emitter, value, &i) {
 				return false
 			}
-			// A break resets indentation so the next line starts fresh;
-			// a trailing break therefore leaves the closing quote at
-			// column zero.
-			emitter.indention = true
-			emitter.whitespace = true
+			// No indentation reset here: it dedented the continuation
+			// after a trailing blank line, and the closing quote itself
+			// (#2819). The double-quoted writer's break handling has no
+			// reset either.
 			previous_break = true
 		} else {
--- a/pkg/yqlib/operator_style_test.go
+++ b/pkg/yqlib/operator_style_test.go
@@ -212,3 +212,20 @@ var styleOperatorScenarios = []expressionScenario{
+	{
+		description: "single-quoted multi-line scalar with trailing blank line round-trips (#2819)",
+		document: "paths:\n  /v1/quack:\n    get:\n      description: '\n        Get quacked.\n\n        - Duck\n\n        '\n",
+		expression: ".",
+		expected: []string{
+			"D0, P[], (!!map)::paths:\n  /v1/quack:\n    get:\n      description: '\n        Get quacked.\n\n        - Duck\n\n        '\n",
+		},
+	},
```

### Test evidence

Repro re-run on the branch. Before (4.53.3):

```
$ yq . source.yml
paths:
  /v1/quack:
    get:
      description: ' Get quacked.

        - Duck

'
```

After (branch build):

```
$ ./yq . source.yml
paths:
  /v1/quack:
    get:
      description: '
        Get quacked.

        - Duck

        '
$ diff <(./yq . source.yml) source.yml && echo IDENTICAL
IDENTICAL
```

Expected-after per the plan: byte-identical round-trip. Controls
(double-quoted twin; single-quoted without the trailing blank line)
unchanged. `go test ./...` passes (4108 tests).
