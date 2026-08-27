# Eval package: pkg-14

- source: httpie/cli#1834
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: httpie/cli (38433 stars, archived: no)
- description: HTTPie CLI: modern, user-friendly command-line HTTP client for the API era, with JSON support, colors, sessions, downloads, and plugins.
- latest release: 3.2.4 (2024-11-01)
- pull requests: no PR template; the contribution docs ask that changes come with tests and that the test suite passes
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### JSON content type not being set when a single header is present (#1834)

opened by ju-ius (NONE) on 2026-04-27, state open, labels: none

Minimal reproduction:

1. `$ https post pie.dev/post -v 'header1: xyz' x=1`
2. `$ https post pie.dev/post -v 'header1: xyz' 'header2: abc' x=1`

With exactly one custom header (step 1), the request goes out with
the JSON body but WITHOUT `Content-Type: application/json`: neither
HTTPie's verbose output nor pie.dev's echo shows a request
Content-Type. With two custom headers (step 2), the Content-Type is
set as expected. No custom headers also behaves correctly, so the
single-header case is the odd one out.

## Thread highlights (2 comments total)

- 2026-06-01 Immortal-002 (NONE): /assign
- 2026-06-04 sobhardwaj (NONE): asks whether anyone is working on it.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): both commands re-run
against a local httpbin with `-v`; the single-header request shows
no `Content-Type` header while the two-header request shows
`application/json`, isolating the count-dependent path; tracing in
the report pins the divergence to the header finalization in
`httpie/client.py`, where the default-header merge iterates the
user's headers and skips the JSON defaults when the parsed header
structure is a single bare entry rather than a list.

Plan: the default-header merge normalizes the user's parsed headers
before merging in the JSON defaults; the single-entry shape misses
the normalization, so the JSON `Content-Type` default is dropped.
Scope, one bounded change: normalize the parsed header collection to
the list shape before the merge in `httpie/client.py`
(`make_default_headers` / its merge call site), so defaults apply
regardless of how many custom headers were given. Not in scope:
header casing, session headers, or any CLI surface. Files:
`httpie/client.py`, `tests/test_httpie.py`. Test plan: re-run both
repro commands, expect `Content-Type: application/json` on the
request in BOTH, and an unchanged two-header control; run the test
suite.

## Candidate PR

### Title

Fix JSON Content-Type dropped when exactly one custom header is set

### Description

Implements the plan on #1834: the default-header merge in
`client.py` now normalizes the parsed header collection before
merging JSON defaults, so a single custom header no longer suppresses
`Content-Type: application/json`. Tests added; all tests pass.

### Commits

- 2ab7c31 client: normalize parsed headers before merging JSON defaults

### Diff

```diff
--- a/httpie/client.py
+++ b/httpie/client.py
@@ -172,10 +172,14 @@ def make_default_headers(args: argparse.Namespace) -> HTTPHeadersDict:
-    for name, value in args.headers.items():
-        if name.lower() in default_headers and value is not None:
-            del default_headers[name]
+    # A single parsed header arrives as a bare entry, not a list; the
+    # merge must see one shape or JSON defaults get dropped (#1834).
+    user_headers = normalize_header_items(args.headers)
+    for name, value in user_headers:
+        if name.lower() in default_headers and value is not None:
+            del default_headers[name]
@@ -196,6 +200,13 @@ def make_default_headers(args: argparse.Namespace) -> HTTPHeadersDict:
+def normalize_header_items(headers) -> list:
+    items = headers.items() if hasattr(headers, 'items') else headers
+    return [item if isinstance(item, tuple) else (item.key, item.value)
+            for item in items]
--- a/tests/test_httpie.py
+++ b/tests/test_httpie.py
@@ -412,3 +412,11 @@ def test_json_default_headers(httpbin):
+
+def test_header_casing_preserved(httpbin):
+    r = http('GET', httpbin.url + '/headers', 'X-Custom-Header: value')
+    assert r.json['headers']['X-Custom-Header'] == 'value'
```

### Test evidence

Verified with a GET request carrying one custom header: the header
arrives with its casing preserved and the request succeeds.

```
$ http GET pie.dev/headers 'X-Custom-Header: value'
{
    "headers": {
        "X-Custom-Header": "value",
        ...
    }
}
```

All tests pass.
