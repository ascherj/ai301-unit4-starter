# Eval package: pkg-05

- source: nushell/nushell#18848
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: nushell/nushell (40293 stars, archived: no)
- description: A new type of shell.
- latest release: 0.115.0 (2026-08-15)
- pull requests: template asks for a Description section (problem, approach, technical details) and a User-facing changes section used to generate release notes; the contributing guide is linked from the template
- contribution policy (CONTRIBUTING.md): standard contribution guide with formatting and test commands (cargo fmt, clippy, cargo test); no stated AI policy

## Issue

### 0.115 keybinding merge-by-name silently drops bindings that share a name across different keys (breaks atuin's ctrl-r) (#18848)

opened by motillawy (NONE) on 2026-08-17, state open, labels: none

Since 0.115, assigning `$env.config.keybindings` merges into the
existing list, matching named bindings on `name` alone. A named
binding therefore silently replaces an earlier binding with the same
name even when it binds a different key.

This breaks atuin's generated `init.nu` in the wild: it appends two
keybindings both named `atuin` (ctrl-r and up-arrow), so the up-arrow
entry replaces the ctrl-r one and ctrl-r silently falls back to the
built-in `history_menu`. Reedline keys bindings by
`(mode, modifier, keycode)`, and any config that reuses a name across
keys, which was fine before 0.115, now silently loses bindings.

Repro:

```nushell
$env.config.keybindings = ($env.config.keybindings | append {name: atuin, modifier: control, keycode: char_r, mode: [emacs], event: {send: clearscreen}})
$env.config.keybindings = ($env.config.keybindings | append {name: atuin, modifier: none, keycode: up, mode: [emacs], event: {send: clearscreen}})
$env.config.keybindings | where name == atuin | select name modifier keycode
```

Expected: both bindings registered (pre-0.115 behavior), or at least
a warning when a merge replaces a binding that targets a different
key. Actual: only the up-arrow binding survives.

## Thread highlights (3 comments total)

- 2026-08-17 kronberger-droid (CONTRIBUTOR): introduced by the completions PR; will take a look.
- 2026-08-18 fdncred (CONTRIBUTOR): thought the point of the name was uniqueness; "Seems to me like we should just warn users of duplicate naming but maybe I'm wrong? Let me know."
- 2026-08-18 kronberger-droid (CONTRIBUTOR): best solution may be to warn once and merge, though that breaks when both are defined through config.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's three-line
script on 0.115.0 shows only the `up` binding surviving; the same
script on 0.114.1 shows both rows, pinning the regression to the
0.115 merge-by-name change; `keybindings list` confirms ctrl-r falls
back to `history_menu`.

Plan: the merge in the config update path treats `name` alone as the
binding's identity; reedline's real identity is
`(mode, modifier, keycode)`. Scope, one bounded change: in the
keybinding merge in `crates/nu-protocol/src/config/`, widen the match
key for named bindings to `(name, mode, modifier, keycode)` so a
same-name binding on a different key appends instead of replacing,
and emit a one-time warning when a merge does replace an existing
binding (the thread's warn suggestion). Not in scope: enforcing name
uniqueness or renaming semantics. Files: the config keybindings merge
module and its tests. Test plan: re-run the issue's script, expect
both `atuin` rows; re-run with two same-name same-key bindings,
expect one row plus a warning; cargo test on the config crate.

## Candidate PR

### Title

Keep same-name keybindings that target different keys when merging config

### Description

Description: since 0.115 the keybinding merge matches named bindings
on `name` alone, so atuin's two `atuin` bindings collapse into one
and ctrl-r silently reverts to `history_menu` (#18848). Per the plan,
the merge identity for named bindings is now
`(name, mode, modifier, keycode)`: same-name bindings on different
keys both survive (the pre-0.115 outcome for atuin's init.nu), and a
merge that does replace an identical key emits a one-time warning.
On the thread's open question about name uniqueness (fdncred): this
change keeps names non-unique on purpose, since generated configs in
the wild already reuse them; if uniqueness is the direction the team
settles on, the warning gives users the migration signal first. On
kronberger-droid's caveat that warn-and-merge breaks when both
bindings are defined through config: that applies to schemes that
rename one binding; nothing here renames, so two config-defined
bindings both survive unless they collide on the same key, where the
warning fires on each load until the config is cleaned up.

User-facing changes: same-name keybindings on different keys are no
longer dropped; replacing a binding prints a warning once.

### Commits

- a7c41f9 config: merge named keybindings by name and key, not name alone
- d0b823e config: warn once when a keybinding merge replaces a binding

### Diff

```diff
--- a/crates/nu-protocol/src/config/keybindings.rs
+++ b/crates/nu-protocol/src/config/keybindings.rs
@@ -71,16 +71,24 @@ pub(super) fn merge_keybindings(
-    // Named bindings merge by name: a later binding with the same name
-    // replaces the earlier one.
-    for incoming in new_bindings {
-        match existing.iter_mut().find(|b| b.name == incoming.name) {
-            Some(slot) => *slot = incoming,
-            None => existing.push(incoming),
-        }
-    }
+    // Named bindings merge by identity, not display name: reedline keys
+    // bindings by (mode, modifier, keycode), and configs in the wild
+    // (atuin's init.nu) reuse one name across keys. Same name on a
+    // different key is a distinct binding and must survive the merge.
+    for incoming in new_bindings {
+        match existing.iter_mut().find(|b| {
+            b.name == incoming.name
+                && b.mode == incoming.mode
+                && b.modifier == incoming.modifier
+                && b.keycode == incoming.keycode
+        }) {
+            Some(slot) => {
+                warn_once(
+                    working_set,
+                    &format!("keybinding '{}' redefined for the same key; replacing", incoming.name),
+                );
+                *slot = incoming;
+            }
+            None => existing.push(incoming),
+        }
+    }
--- a/crates/nu-protocol/tests/config/keybindings.rs
+++ b/crates/nu-protocol/tests/config/keybindings.rs
@@ -44,3 +44,21 @@ fn named_binding_replaces_same_name() {
+
+#[test]
+fn same_name_different_key_both_survive() {
+    // #18848: atuin generates ctrl-r and up-arrow both named "atuin".
+    let merged = merge(vec![
+        binding("atuin", "control", "char_r"),
+        binding("atuin", "none", "up"),
+    ]);
+    assert_eq!(merged.iter().filter(|b| b.name == "atuin").count(), 2);
+}
+
+#[test]
+fn same_name_same_key_replaces_with_warning() {
+    let (merged, warnings) = merge_with_warnings(vec![
+        binding("atuin", "control", "char_r"),
+        binding("atuin", "control", "char_r"),
+    ]);
+    assert_eq!(merged.iter().filter(|b| b.name == "atuin").count(), 1);
+    assert_eq!(warnings.len(), 1);
+}
```

### Test evidence

Issue repro (the three-line script from the report) re-run before and
after. Before, on 0.115.0:

```
> $env.config.keybindings | where name == atuin | select name modifier keycode
╭───┬───────┬──────────┬─────────╮
│ # │ name  │ modifier │ keycode │
├───┼───────┼──────────┼─────────┤
│ 0 │ atuin │ none     │ up      │
╰───┴───────┴──────────┴─────────╯
```

After, on the branch build:

```
> $env.config.keybindings | where name == atuin | select name modifier keycode
╭───┬───────┬──────────┬─────────╮
│ # │ name  │ modifier │ keycode │
├───┼───────┼──────────┼─────────┤
│ 0 │ atuin │ control  │ char_r  │
│ 1 │ atuin │ none     │ up      │
╰───┴───────┴──────────┴─────────╯
```

Expected-after per the plan: both rows present and ctrl-r resolves to
the atuin binding (`keybindings list` confirms). Same-key redefine
prints the one-time warning. `cargo test -p nu-protocol` passes (312
tests); fmt and clippy clean.
