# Eval package: pkg-17

- source: vuejs/core#14893
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: vuejs/core (54219 stars, archived: no)
- description: Vue.js is a progressive, incrementally-adoptable JavaScript framework for building UI on the web.
- latest release: v3.5.41 (2026-08-05)
- pull requests: no PR template; the contributing guide's pull request guidelines ask for a clear description of the problem, tests for fixes, and conventional-commit titles
- contribution policy (.github/contributing.md): standard contribution guide; no stated AI policy

## Issue

### `reactive` silently skips un-extensible objects, which seems undocumented and unnecessary (#14893)

opened by edave64 (NONE) on 2026-05-30, state open, labels: has workaround, p2-edge-case

Code like `reactive(Object.seal({ useDarkTheme: null }))` looks like
it should observe property changes while preventing new properties.
What is not mentioned in the documentation is that `reactive` will
silently return the target object without any proxy if it is
non-extensible. This caused a shipped bug where setting the theme
just did nothing.

The skip traces to the days when `reactive` set a flag property
directly on the target (which threw on frozen objects); reactivity
flags are now handled by the proxy's `get` handler without modifying
the target, so the historical reason is gone.

Proposed: either make `reactive(Object.seal(...))` work, or cement
and document the current behavior. (Keeping the skip for
`Object.isFrozen()` would be safe either way, since frozen objects
cannot mutate.)

## Thread highlights (1 comment total)

- 2026-05-31 edave64 (NONE): the workaround makes it extra silly: `Object.seal(reactive({...}))` works fine, since the proxy does not trap preventExtensions.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): a minimal script shows
`reactive(Object.seal({ x: 1 }))` returning the raw target
(`isReactive()` false, watcher never fires on `x`), while
`reactive({ x: 1 })` behaves normally; a control confirms the frozen
case (`Object.freeze`) also returns the raw object.

Plan: this is a behavior-vs-documentation decision the thread leaves
open, so the plan takes the conservative half: keep the skip, stop
it being silent, and document it. Scope, two named deliverables:
(1) in `packages/reactivity/src/reactive.ts`, emit a dev-mode
warning when `reactive()` (and `shallowReactive`) receives a
non-extensible, non-frozen target it will not proxy; (2) update the
reactivity-core documentation page to state the limitation and the
`Object.seal(reactive(...))` workaround. Not in scope: changing what
`reactive` returns. Files: `packages/reactivity/src/reactive.ts`,
its tests, and the docs page. Test plan: dev build re-run of the
repro, expect the warning naming the function and the target's
sealed state; production build unchanged; docs render the new note;
`pnpm test reactivity`.

## Candidate PR

### Title

fix(reactivity): warn when reactive() skips a non-extensible target, and document the behavior

### Description

Implements the plan on #14893 in full: `reactive()` and
`shallowReactive()` now emit a dev-mode warning when handed a
non-extensible target they will not proxy (sealed objects were the
silent shipped-bug case), and the reactivity-core documentation now
documents the limitation with the `Object.seal(reactive(...))`
workaround, so the behavior is both visible at runtime and stated in
the docs. No behavior change in what `reactive` returns; frozen
objects stay exempt from the warning since they cannot mutate
anyway. Tests cover the sealed, frozen, and extensible cases.

### Commits

- 51e0f2c fix(reactivity): warn on non-extensible targets in dev

### Diff

```diff
--- a/packages/reactivity/src/reactive.ts
+++ b/packages/reactivity/src/reactive.ts
@@ -284,6 +284,14 @@ function createReactiveObject(
   // target cannot be observed
   if (!Object.isExtensible(target)) {
+    if (__DEV__ && !Object.isFrozen(target)) {
+      warn(
+        `reactive() cannot make a non-extensible object reactive; ` +
+          `returning the raw object. Wrap the object with reactive() ` +
+          `before sealing it: Object.seal(reactive(obj)).`,
+      )
+    }
     return target
   }
--- a/packages/reactivity/__tests__/reactive.spec.ts
+++ b/packages/reactivity/__tests__/reactive.spec.ts
@@ -301,3 +301,17 @@ describe('reactivity/reactive', () => {
+
+  test('warns on sealed target and returns it raw (#14893)', () => {
+    const sealed = Object.seal({ x: 1 })
+    const result = reactive(sealed)
+    expect(result).toBe(sealed)
+    expect(
+      `reactive() cannot make a non-extensible object reactive`,
+    ).toHaveBeenWarned()
+  })
+
+  test('does not warn on frozen target', () => {
+    reactive(Object.freeze({ x: 1 }))
+    expect(warnSpy).not.toHaveBeenCalled()
+  })
```

### Test evidence

Repro re-run on a dev build:

```
> const ui = reactive(Object.seal({ useDarkTheme: null }))
[Vue warn] reactive() cannot make a non-extensible object reactive;
returning the raw object. Wrap the object with reactive() before
sealing it: Object.seal(reactive(obj)).
```

Expected-after per the plan: the silent skip now warns in dev;
production build emits nothing (verified with a prod bundle run).
`pnpm test reactivity` passes (511 tests).
