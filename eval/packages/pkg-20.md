# Eval package: pkg-20

- source: ghostty-org/ghostty#13604
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: ghostty-org/ghostty (59840 stars, archived: no)
- description: Ghostty is a fast, feature-rich, and cross-platform terminal emulator that uses platform-native UI and GPU acceleration.
- latest release: v1.3.1
- pull requests: no PR template; first-time contributors go through a vouch flow before PRs are accepted
- contribution policy (CONTRIBUTING.md + AI_POLICY.md): strict AI rules. All AI usage in any form must be disclosed, stating the tool used and the extent of the assistance; the human in the loop must fully understand the work; AI-assisted issues and comments must be reviewed and edited by a human before submission

## Issue

### Mode 2031 reports do not work unless both a dark and a light theme are configured (#13604)

opened by jcollie (MEMBER) on 2026-08-04, state open, labels: vt, gtk

With an isolated debug instance launched as
`ghostty --config-default-files=false --window-theme=dark`, the GTK
log correctly reports `style manager changed scheme=.dark`, but
querying the color scheme with `CSI ? 996 n` returns
`CSI ? 997 ; 2 n` (light mode). With an actual conditional theme
pair configured (`theme = light:Rose Pine Dawn,dark:Rose Pine`), the
same query correctly returns `CSI ? 997 ; 1 n`.

The issue is in `Config.changeConditionalState`: the function only
rebuilds the configuration when the changed state key is present in
`_conditional_set`. A single non-conditional theme
(`theme = Kitty Default`) does not add `.theme` to that set, so
changing the application color scheme from the default `.light` to
`.dark` is treated as irrelevant and the function returns null. The
surface and GTK runtime know the scheme is dark, but the
configuration copied into Termio retains its default
`_conditional_state.theme = .light`, and the mode-2031 response
reads the theme from the Termio configuration. A minimal patch
(included in the report) treats the theme state as relevant even
when the configured theme is not conditional, and updates the
existing test.

## Thread highlights (0 comments total)

(no comments)

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's isolated
launch re-run on a debug build; `printf '\033[?996n'` returns
`?997;2n` under `--window-theme=dark` with a single theme, and
`?997;1n` once a conditional pair is configured, matching the
issue's isolation exactly.

Plan: adopt the issue author's diagnosis and minimal patch shape (a
maintainer wrote the issue, so the direction is settled). Scope, one
bounded change: in `src/config/Config.zig`,
`changeConditionalState` treats a color-scheme state change as
relevant even when `.theme` is absent from `_conditional_set`, so
the rebuilt config carries the true scheme into Termio and mode-2031
reports it correctly; update the existing conditional-state test the
way the issue sketches. Not in scope: the GTK style-manager plumbing
or the query implementation. Files: `src/config/Config.zig` and its
test block. Test plan: re-run the repro query under
`--window-theme=dark` with a single theme, expect `?997;1n`; the
conditional-pair control unchanged; `zig build test`.

## Candidate PR

### Title

config: rebuild conditional state on scheme change with non-conditional themes

### Description

Implements the fix sketched in #13604: `changeConditionalState` now
treats a color-scheme change as relevant even when the configured
theme is not conditional, so the Termio config carries the real
scheme and `CSI ? 996 n` reports it correctly with a single theme
configured. The existing conditional-state test is updated per the
issue, and a second case covers the single-theme scheme flip. Repro
evidence below; `zig build test` passes.

### Commits

- 77d0b4c config: scheme changes are relevant even without conditional themes

### Diff

```diff
--- a/src/config/Config.zig
+++ b/src/config/Config.zig
@@ -4413,10 +4413,13 @@ pub fn changeConditionalState(
-            // Conditional state changes are only relevant if the
-            // configuration uses the changed key in a conditional.
-            if (!self._conditional_set.contains(key)) return null;
+            // The theme state is always relevant to a color-scheme
+            // change: even a non-conditional theme must carry the true
+            // scheme into the derived config, or mode 2031 reports the
+            // default .light forever (#13604).
+            if (key != .theme and !self._conditional_set.contains(key))
+                return null;
@@ -5126,16 +5129,30 @@ test "changeConditionalState ignores irrelevant changes" {
-test "changeConditionalState returns null without conditional theme" {
-    var cfg = try Config.default(alloc);
-    defer cfg.deinit();
-    try cfg.parse("theme = Kitty Default");
-    const result = try cfg.changeConditionalState(.{ .theme = .dark });
-    try testing.expect(result == null);
-}
+test "changeConditionalState rebuilds for scheme change without conditional theme" {
+    var cfg = try Config.default(alloc);
+    defer cfg.deinit();
+    try cfg.parse("theme = Kitty Default");
+    const result = try cfg.changeConditionalState(.{ .theme = .dark });
+    try testing.expect(result != null);
+    try testing.expectEqual(.dark, result.?._conditional_state.theme);
+}
+
+test "changeConditionalState still ignores unrelated keys" {
+    var cfg = try Config.default(alloc);
+    defer cfg.deinit();
+    try cfg.parse("theme = Kitty Default");
+    const result = try cfg.changeConditionalState(.{ .fullscreen = true });
+    try testing.expect(result == null);
+}
```

### Test evidence

Repro re-run on the branch (debug build, isolated config):

```
$ ghostty --config-default-files=false --window-theme=dark &
$ printf '\033[?996n'      # before: ESC[?997;2n (light)
$ printf '\033[?996n'      # after:  ESC[?997;1n (dark)
```

Expected-after per the plan: `?997;1n` with a single non-conditional
theme under a dark window theme; the conditional-pair control still
returns `?997;1n`. `zig build test` passes (config suite included).
