# Eval package: pkg-10

- source: laurent22/joplin#16215
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: laurent22/joplin (56002 stars, archived: no)
- description: Joplin - the privacy-focused note taking app with sync capabilities for Windows, macOS, Linux, Android and iOS.
- latest release: v3.6.15 (2026-06-20)
- pull requests: no PR template; the contributing guide asks that PRs reference the issue, keep changes minimal, and pass the test suite (yarn test)
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### WebDAV sync ETIMEDOUT returns in 3.7.10: 250 ms autoSelectFamily timeout aborts slow connections (#16215)

opened by PandaWood (NONE) on 2026-08-16, state open, labels: bug

Follow-up to #16201: the previous fix (#15983) addressed Koofr's 405
rejection of the `If-None-Match` header, which cannot produce an
`ETIMEDOUT`; the timeout symptom has a separate root cause that still
reproduces on 3.7.10.

Sync fails intermittently with
`FetchError: request to https://app.koofr.net/... failed, reason: Code: ETIMEDOUT`
while `curl` and a current system Node succeed instantly against the
same URL. Root cause: Node's Happy Eyeballs implementation
(`autoSelectFamily`) races connection attempts across all resolved
addresses, aborting each attempt after
`autoSelectFamilyAttemptTimeout`; Joplin's bundled runtime defaults
that to 250 ms. `app.koofr.net` resolves to two A records and TCP
connect from the reporter's location consistently takes 320-360 ms,
so every attempt is aborted. Environment: Joplin 3.7.10 AppImage,
Electron 42.3.0, bundled Node 24.15.0, Arch Linux.

## Thread highlights (7 comments total)

- 2026-08-17 mrjo118 (COLLABORATOR): asks whether other clients get decent speed from Koofr; probing VPN or distance as factors.
- 2026-08-17 PandaWood (NONE): notes that treating over-250ms connects as "bad servers" would rule out intercontinental WebDAV use generally.
- 2026-08-17 PandaWood (NONE): background: Node took 250 ms from RFC 8305 but not the algorithm; in the RFC it starts a parallel fallback, in Node it aborts the attempt.
- 2026-08-17 mrjo118 (COLLABORATOR): has made a code change to try to fix this and built a development binary for Windows for testing.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): with the bundled runtime,
`getDefaultAutoSelectFamilyAttemptTimeout()` prints 250; syncing
against a WebDAV endpoint whose TCP connect is delayed to ~350 ms
(tc netem in the report) fails with the empty-reason ETIMEDOUT on
3.7.10, while the same target syncs cleanly with the delay removed,
isolating the attempt timeout as the trigger.

Plan: raise the auto-select-family attempt timeout for Joplin's
network stack rather than disabling the mechanism. Scope, one
bounded change: in the desktop app's node-fetch agent setup
(`packages/lib/shim-init-node.ts`), set
`autoSelectFamilyAttemptTimeout` to 2000 ms on the agents used for
sync requests, keeping Happy Eyeballs enabled. Not in scope: mobile,
the request layer's retry logic, or per-target configuration. Files:
`packages/lib/shim-init-node.ts`, one unit test asserting the agent
option. Test plan: re-run the delayed-connect repro, expect sync to
succeed with the 350 ms connect (before: ETIMEDOUT; after: success),
and `yarn test` on the lib package.

## Candidate PR

### Title

Fix WebDAV ETIMEDOUT on slow connections: raise autoSelectFamily attempt timeout

### Description

Fixes #16215. Node's default 250 ms `autoSelectFamilyAttemptTimeout`
aborts connection attempts to servers whose TCP connect takes longer,
which is routine for intercontinental WebDAV targets. The sync
agents now use a 2000 ms attempt timeout, keeping Happy Eyeballs
enabled, per the plan on the thread. Verified working: I have been
syncing against Koofr for a full day on this build with no timeouts.

### Commits

- 5d19c02 shim: raise autoSelectFamilyAttemptTimeout to 2000ms for sync agents

### Diff

```diff
--- a/packages/lib/shim-init-node.ts
+++ b/packages/lib/shim-init-node.ts
@@ -204,12 +204,18 @@ function setupProxySettings(options: ProxySettings) {
 const httpAgent_ = new http.Agent({
     keepAlive: true,
     maxSockets: 10,
+    // Node aborts each Happy Eyeballs connection attempt after
+    // autoSelectFamilyAttemptTimeout (default 250 ms), which kills
+    // intercontinental WebDAV connects outright (#16215). Keep the
+    // mechanism, give attempts room to actually connect.
+    autoSelectFamilyAttemptTimeout: 2000,
 });
 
 const httpsAgent_ = new https.Agent({
     keepAlive: true,
     maxSockets: 10,
+    autoSelectFamilyAttemptTimeout: 2000,
 });
--- a/packages/lib/shim-init-node.test.ts
+++ b/packages/lib/shim-init-node.test.ts
@@ -66,3 +66,10 @@ describe('shim-init-node', () => {
+
+    it('sync agents allow slow connects under autoSelectFamily', () => {
+        const { httpAgent, httpsAgent } = testAgents();
+        expect(httpAgent.options.autoSelectFamilyAttemptTimeout).toBe(2000);
+        expect(httpsAgent.options.autoSelectFamilyAttemptTimeout).toBe(2000);
+    });
```

### Test evidence

Verified working on my machine: a full day of WebDAV syncs against
Koofr on this build with zero ETIMEDOUT errors. The change is a
two-line agent option, so no further testing seemed necessary.
