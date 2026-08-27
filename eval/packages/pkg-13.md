# Eval package: pkg-13

- source: neovim/neovim#41337
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: neovim/neovim (101857 stars, archived: no)
- description: Vim-fork focused on extensibility and usability.
- latest release: v0.12.4 (2026-07-05)
- pull requests: template asks for a Problem section and a Solution section; the contributing guide's PR rules (commit message conventions, tests for behavior changes) are linked from the template
- contribution policy (CONTRIBUTING.md): standard contribution guide; no stated AI policy

## Issue

### `vim.ui.open()` URL truncation on Windows when URL contains `&` (#41337)

opened by mxlnmist (NONE) on 2026-08-16, state open, labels: platform:windows, ui

When `vim.ui.open()` is called with a URL that includes an ampersand
in the query string, the browser opens only the part before the first
`&`:

```lua
vim.ui.open("https://duckduckgo.com/?q=hello&t=brave")
```

opens `https://duckduckgo.com/?q=hello`, and `&t=brave` is lost.
`:wait()` on the returned SystemObj shows exit code 1 with stderr
`'t' is not recognized as an internal or external command`, even
though the spawned command is
`{ "cmd.exe", "/c", "start", "", "https://duckduckgo.com/?q=hello&t=brave" }`.

Steps: `nvim --clean`, then
`:lua vim.ui.open("https://duckduckgo.com/?q=hello&t=brave")`.
Expected: the full URL opens. Environment: v0.13.0-dev nightly,
Windows 11, Wezterm.

## Thread highlights (0 comments total)

(no comments)

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's command
re-run on the nightly shows the truncated URL in the browser and the
`'t' is not recognized` stderr; a control without `&`
(`?q=hello`) opens fully, and quoting the URL manually in a raw
`cmd.exe /c start "" "URL^&t=brave"` opens the full URL, isolating
cmd.exe's metacharacter parsing of the unquoted argument as the
cause.

Plan: cmd.exe re-parses the argument string after `/c`, so `&` (and
its sibling metacharacters `^ | < >`) split the command even though
the URL was passed as one argv entry. Scope, one bounded change: in
`runtime/lua/vim/ui.lua`, when building the Windows `cmd.exe /c
start` invocation, caret-escape the cmd metacharacters in the path
or URL argument. Known limit, stated in the plan: `%` (environment
expansion, e.g. `%20` in pre-encoded URLs followed by an existing
variable name) has different escaping rules under `/c` and is NOT
covered by this change; if it proves messy it will be deferred with
a note. Files: `runtime/lua/vim/ui.lua`,
`test/functional/lua/ui_spec.lua`. Test plan: re-run the repro,
expect the full URL (both query parameters) in the browser and exit
code 0 from `:wait()`; the no-ampersand control unchanged; run the
ui functional spec.

## Candidate PR

### Title

fix(ui): escape cmd.exe metacharacters in vim.ui.open() on Windows

### Description

Problem: `vim.ui.open("...?q=hello&t=brave")` on Windows truncates
at `&`: cmd.exe re-parses the argument after `/c`, so metacharacters
split the start command (#41337).

Solution: caret-escape the cmd metacharacters (`& ^ | < >`) in the
argument when building the `cmd.exe /c start` invocation, per the
plan posted on the issue. Deviation note, recorded in the plan
before this PR: percent-sign environment expansion (`%VAR%`) is NOT
handled here; its escaping rules under `/c` differ (doubling vs
caret) and a URL like `?q=%PATH%` still expands. The plan's deferral
note covers it, and this description restates it so reviewers can
weigh the limit.

### Commits

- fd83a12 fix(ui): caret-escape cmd.exe metacharacters in vim.ui.open()

### Diff

```diff
--- a/runtime/lua/vim/ui.lua
+++ b/runtime/lua/vim/ui.lua
@@ -155,9 +155,18 @@ function M.open(path, opt)
   elseif vim.fn.has('win32') == 1 then
-    cmd = { 'cmd.exe', '/c', 'start', '""', path }
+    -- cmd.exe re-parses the argument after /c, so & | ^ < > split the
+    -- start command even when the URL is a single argv entry (#41337).
+    -- Caret-escape them. Deliberately not handled: %VAR% expansion,
+    -- whose /c escaping rules differ (see the plan's deferral note).
+    local escaped = path:gsub('[&|^<>]', '^%0')
+    cmd = { 'cmd.exe', '/c', 'start', '""', escaped }
--- a/test/functional/lua/ui_spec.lua
+++ b/test/functional/lua/ui_spec.lua
@@ -101,3 +101,17 @@ describe('vim.ui.open()', function()
+
+  it('escapes cmd.exe metacharacters on Windows', function()
+    skip(not is_os('win'), 'Windows only')
+    -- #41337: & in a query string must survive cmd.exe /c start.
+    local cmd
+    exec_lua([[
+      vim.system = function(c) _G._cmd = c; return { wait = function() return { code = 0 } end } end
+      vim.ui.open('https://example.com/?q=hello&t=x')
+    ]])
+    cmd = exec_lua('return _G._cmd')
+    eq('https://example.com/?q=hello^&t=x', cmd[#cmd])
+  end)
```

### Test evidence

Repro re-run on the branch (Windows 11):

```
:lua =vim.ui.open("https://duckduckgo.com/?q=hello&t=brave"):wait()
-- before: { code = 1, stderr = "'t' is not recognized ..." },
--         browser shows https://duckduckgo.com/?q=hello
-- after:  { code = 0, stderr = "" },
--         browser shows https://duckduckgo.com/?q=hello&t=brave
```

Expected-after per the plan: both query parameters present, exit
code 0. No-ampersand control unchanged. `TEST_FILE=test/functional/lua/ui_spec.lua make functionaltest`
passes, including the new case.
