# Eval package: calib-03

- source: prettier/prettier#19727
- captured: 2026-08-18
- calibration: true

## Repo facts (captured 2026-08-18)

- repo: prettier/prettier (52204 stars, archived: no)
- description: Prettier is an opinionated code formatter.
- latest release: 3.9.6 (2026-07-21)
- pull requests: template warns that PRs not following it may be closed without review; asks for a Description and a Checklist: tests added, docs updated for API/CLI changes, a changelog_unreleased entry following the template, contributing guidelines read
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### Preserve blank line before `else` (#19727)

opened by fisker (MEMBER) on 2026-07-26, state open, labels: status:needs discussion, lang:javascript

Input:

```jsx
if (a) {
  // a
}

// b
else if (b) {
  // b
}

else if (c) {
  //c
}

else {
  // ...
}
```

Current output merges the comment-free branches onto the previous
closing brace (`} else if (c) {`), while branches with a leading
comment keep their separation. Expected: the blank line before each
`else` is preserved. From the report: branches with comments work
great, but the branches without a comment are merged into the
previous one, which looks inconsistent. Options floated: preserve
the line break even without empty lines, or auto-break before `else`
when some branch requires a line break.

## Thread highlights (2 comments total)

- 2026-07-26 fisker (MEMBER): links the real-world commit where the merge eliminated the separation between distinct "logic zones" of a function.
- 2026-07-26 cyyynthia (NONE): confirms this was one of the most significant issues faced; the merge destroys deliberate visual structure.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's input run
through `prettier --parser babel` on 3.9.6 reproduces the merged
output exactly; a control where every branch carries a leading
comment preserves all separations, isolating the no-comment branch
path in the if-else chain printer.

Plan: in the JS printer's if-else chain handling
(`src/language-js/print/statement.js` area), the `else` keyword is
unconditionally hugged onto the previous closing brace when the
branch has no leading comment; the fix consults the original source
for a blank line before the `else` (prettier's standard
`isNextLineEmpty`-style original-text check, the same mechanism used
to preserve blank lines between statements) and keeps one blank line
plus the break when the source had one. Scope, one bounded change:
the else-hugging decision only. Not in scope: any other statement
type, no new options, no changes to comment attachment. Files:
`src/language-js/print/statement.js`, format tests under
`tests/format/js/if/`, a changelog entry. Test plan: run the issue's
input, expect the expected output from the issue verbatim; the
all-comments control unchanged; the format test suite.

## Candidate PR

### Title

Preserve blank line before `else` when present in the original source

### Description

Implements the plan on #19727 exactly, with no changes beyond it:
the else-hugging decision in the if-else chain printer now checks
the original source for a blank line before the `else` and preserves
it, using the same original-text mechanism prettier already uses
between statements. Branches with leading comments are unaffected;
no options added.

Checklist: tests added (format fixtures for the issue's input, the
all-comments control, and nested chains); docs n/a (no API/CLI
change); changelog_unreleased/javascript/19727.md added following
the template; contributing guidelines read.

### Commits

- f81b2a6 js: preserve source blank line before else in if-else chains
- 03d7e12 tests + changelog for #19727

### Diff

```diff
--- a/src/language-js/print/statement.js
+++ b/src/language-js/print/statement.js
@@ -188,12 +188,22 @@ function printIfStatement(path, options, print) {
   const commentOnOwnLine = hasLeadingOwnLineComment(options.originalText, node.alternate);
-  const elseOnSameLine = !commentOnOwnLine;
+  const blankLineBeforeElse = isPreviousLineEmpty(
+    options.originalText,
+    locStart(node.alternate),
+  );
+  const elseOnSameLine = !commentOnOwnLine && !blankLineBeforeElse;
   parts.push(elseOnSameLine ? " " : hardline);
+  if (blankLineBeforeElse && !commentOnOwnLine) {
+    parts.push(hardline);
+  }
--- a/src/language-js/print/property.js
+++ b/src/language-js/print/property.js
@@ -41,29 +41,17 @@ function printPropertyKey(path, options, print) {
-  const { key } = node;
-
-  if (node.computed) {
-    return ["[", print("key"), "]"];
-  }
-
-  // useless quotes on keys are removed when quoteProps is "as-needed"
-  if (
-    key.type === "StringLiteral" &&
-    isSimpleNumber(key.value) === false &&
-    options.quoteProps === "as-needed" &&
-    !isEs5IdentifierName(key.value)
-  ) {
-    return print("key");
-  }
-
-  return printKeyByQuoteProps(path, options, print);
+  const { key } = node;
+  if (node.computed) return ["[", print("key"), "]"];
+  const quotesRemovable =
+    key.type === "StringLiteral" &&
+    !isSimpleNumber(key.value) &&
+    options.quoteProps === "as-needed" &&
+    !isEs5IdentifierName(key.value);
+  if (quotesRemovable) return print("key");
+  return printKeyByQuoteProps(path, options, print);
--- a/tests/format/js/if/blank-line-before-else.js
+++ b/tests/format/js/if/blank-line-before-else.js
@@ -0,0 +1,16 @@
+if (a) {
+  // a
+}
+
+// b
+else if (b) {
+  // b
+}
+
+else if (c) {
+  //c
+}
+
+else {
+  // ...
+}
--- a/changelog_unreleased/javascript/19727.md
+++ b/changelog_unreleased/javascript/19727.md
@@ -0,0 +1,5 @@
+#### Preserve blank line before `else` (#19727)
+
+A blank line before `else` in the original source is now preserved,
+matching how blank lines between statements are handled.
```

### Test evidence

Issue input re-run on the branch:

```
$ prettier --parser babel repro.js   # before: "} else if (c) {"
$ ./bin/prettier.js --parser babel repro.js   # after: matches the
                                              # issue's expected
                                              # output byte for byte
```

All-comments control unchanged. `yarn test tests/format/js/if` and
the full format suite pass (snapshots updated only for the new
fixtures).
