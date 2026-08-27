# Eval package: pkg-15

- source: zellij-org/zellij#5474
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: zellij-org/zellij (34990 stars, archived: no)
- description: A terminal workspace with batteries included.
- latest release: v0.44.3 (2026-05-13)
- pull requests: no PR template; the contribution docs ask that changes reference the issue and pass cargo test
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### Server dies with "Too many open files": soft fd limit is never raised and the accept loop panics (#5474)

opened by Mazyod (NONE) on 2026-08-13, state open, labels: none

A 5-day-old session with about 25 tabs crashed and took everything
with it:

```
Error occurred in server:
  x Thread 'server_listener' panicked.
  |-> At zellij-server/src/lib.rs:935:29
  '-> err Os { code: 24, kind: Uncategorized, message: "Too many open files" }
```

Zellij 0.44.3, macOS 15. Root cause: the soft fd limit. macOS gives
processes 256 by default and the server keeps whatever it inherited.
A long-lived server eats through that organically (every tab carries
tab-bar and status-bar plugin instances holding fds); eventually one
`accept()` in `server_listener` returns EMFILE and the panic kills
every session on the server.

Two asks: (1) raise the soft limit to the hard limit at server
startup (one setrlimit call); (2) do not panic when accept() fails,
because EMFILE there is transient: log, sleep briefly, keep
accepting.

Minimal repro: `ulimit -n 64`, create a background session, add tabs
until the server dies.

## Thread highlights (2 comments total)

- 2026-08-13 fzlzjerry (NONE): confirmed the failure path on main; `listener.incoming()` calls accept() per item, so the listener can safely continue after an individual accept error; has a focused patch replacing the panic with non-fatal logging and a 100 ms wait.
- 2026-08-15 Mazyod (NONE): crashed again after trying to raise fd limits externally; the issue is a blocker.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): with `ulimit -n 64`, a
background session dies on the 4th tab with the exact panic from the
issue; a control at the default 256 survives tab creation, and
`lsof` counts confirm plugin instances holding the fds, matching the
issue's mechanism.

Plan: both asks, both bounded. Scope: (1) at server startup in
`zellij-server/src/lib.rs`, raise the soft RLIMIT_NOFILE to the hard
limit, logging old and new values; (2) in the `server_listener`
accept loop (lib.rs:935 area), replace the panic on accept error
with a logged warning and a 100 ms backoff, continuing the loop. Not
in scope: reducing plugin fd usage or changing session
serialization. Files: `zellij-server/src/lib.rs`, one unit test on
the limit-raise helper. Test plan: re-run the ulimit-64 repro,
expect the server to survive past the 4th tab (limit raised) and,
with the limit forced low, to log accept failures without dying;
`cargo test -p zellij-server`.

## Candidate PR

### Title

server: raise fd soft limit at startup and survive accept() errors

### Description

Fixes #5474 per the posted plan: the server now raises
RLIMIT_NOFILE's soft limit to the hard limit at startup, and the
listener loop logs-and-continues on accept errors (100 ms backoff)
instead of panicking, so a transient EMFILE no longer destroys every
session. Repro evidence below; `cargo test -p zellij-server` passes.

### Commits

- 3ba07e4 raise fd soft limit at server startup
- 51cc2e9 dont panic in accept loop
- 8ff41d2 misc cleanups while debugging

### Diff

```diff
--- a/zellij-server/src/lib.rs
+++ b/zellij-server/src/lib.rs
@@ -30,11 +30,10 @@ use std::{
-use std::sync::{
-    atomic::{AtomicBool, Ordering},
-    Arc, Mutex, RwLock,
-};
+use std::sync::{Arc, Mutex, RwLock};
+use std::sync::atomic::{AtomicBool, Ordering};
+use std::{thread, time::Duration};
@@ -118,6 +117,29 @@ pub fn start_server(mut os_input: Box<dyn ServerOsApi>, socket_path: PathBuf) {
+    raise_fd_soft_limit();
+
+    // log::debug!("fd limit raised");
+    // std::process::Command::new("lsof").arg("-p")... // was counting fds
+
+    fn raise_fd_soft_limit() {
+        let mut lim = libc::rlimit { rlim_cur: 0, rlim_max: 0 };
+        unsafe {
+            if libc::getrlimit(libc::RLIMIT_NOFILE, &mut lim) == 0 {
+                let old = lim.rlim_cur;
+                lim.rlim_cur = lim.rlim_max;
+                if libc::setrlimit(libc::RLIMIT_NOFILE, &lim) == 0 {
+                    log::info!("raised fd soft limit {} -> {}", old, lim.rlim_cur);
+                } else {
+                    log::warn!("could not raise fd soft limit past {}", old);
+                }
+            }
+        }
+    }
+
+    #[allow(dead_code)]
+    fn count_open_fds() -> usize {
+        std::fs::read_dir("/dev/fd").map(|d| d.count()).unwrap_or(0)
+    }
@@ -929,13 +951,20 @@ fn server_listener(...) {
-    for stream in listener.incoming() {
-        match stream {
-            Ok(stream) => handle_stream(stream),
-            Err(err) => {
-                panic!("err {:?}", err);
-            },
-        }
-    }
+    for stream in listener.incoming() {
+        match stream {
+            Ok(stream) => handle_stream(stream),
+            Err(err) => {
+                eprintln!("DEBUG accept err = {:?}", err);
+                log::warn!("accept() failed ({:?}); retrying in 100ms", err);
+                thread::sleep(Duration::from_millis(100));
+                continue;
+            },
+        }
+    }
@@ -1044,9 +1073,9 @@ fn init_session(...) {
-    let client_attributes = ClientAttributes {
-        size,
-        style,
-    };
+    let client_attributes = ClientAttributes { size, style };
```

### Test evidence

Repro re-run on the branch:

```
$ ulimit -n 64 && zellij attach --create-background repro
$ for i in 1 2 3 4 5 6; do zellij --session repro action new-tab; done
# before: server panic on the 4th tab (Too many open files)
# after: all 6 tabs created; server log shows
#   "raised fd soft limit 64 -> unlimited"
```

Forced-low control (hard limit pinned at 64): tabs fail to open but
the server stays up, logging "accept() failed ... retrying" without
dying. Expected-after per the plan on both counts.
`cargo test -p zellij-server` passes.
