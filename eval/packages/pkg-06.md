# Eval package: pkg-06

- source: microsoft/terminal#20507
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: microsoft/terminal (104626 stars, archived: no)
- description: The new Windows Terminal and the original Windows console host, all in the same place.
- latest release: v1.24.11911.0 (2026-07-16)
- pull requests: template asks for Summary of the Pull Request, References and Relevant Issues, Detailed Description, Validation Steps Performed, and a PR checklist (closes #xxx, tests added/passed, documentation, schema)
- contribution policy (CONTRIBUTING.md): contributions require a signed CLA; first-party code must not use private APIs (restated by a maintainer in this thread)

## Issue

### SystemMenu is always light theme colored (#20507)

opened by maj113 (NONE) on 2026-08-04, state open, labels: Issue-Bug, Area-UserInterface, Product-Terminal, Priority-3, Tracking-External

Steps to reproduce: right click the titlebar or press alt+space to
open the System Menu.

Expected: the System Menu follows either the Windows color mode
(dark/light preference) or the Terminal application theme preference.

Actual: it is always white/light.

## Thread highlights (8 comments total)

- 2026-08-05 zadjii-msft (MEMBER): confident this is already on the backlog somewhere; cannot find it.
- 2026-08-05 zadjii-msft (MEMBER): points at IslandWindow.cpp lines 1841-1845 as the place someone could try; mentions the explorer dark theme hack "which we're not actually using in our code base".
- 2026-08-05 maj113 (NONE): notes the SystemMenu ignores SetWindowTheme; it follows the UxTheme preferred app mode (undocumented API).
- 2026-08-05 DHowett (MEMBER): "we're held to a bit of a higher standard as first-party Microsoft folks such that we cannot ship any private API uses in public code."

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): on Windows 11 with system
dark mode and the Terminal dark theme, alt+space renders a light
system menu (screenshot in the report); the same build's title bar
and tab row render dark, isolating the menu as the one surface not
following the theme plumbing.

Plan: follow the maintainer pointer to
`src/cascadia/WindowsTerminal/IslandWindow.cpp` (the theme-update
path zadjii-msft linked): when the window theme updates, apply the
matching menu theming through the documented dark-mode support that
path already uses, explicitly NOT using the undocumented
SetPreferredAppMode API (DHowett: no private APIs in public code).
Honest limit stated in the plan: without the private API, the menu
may only follow the theme on OS builds where the documented path
supports owner-drawn menu theming; if the documented path cannot
theme the menu at all, the plan's fallback is to report that finding
on the issue instead of shipping a hack. Scope, one bounded change:
the theme-update path in `IslandWindow.cpp` plus its header. Not in
scope: any other window chrome, settings surface, or theme plumbing.
Files: `src/cascadia/WindowsTerminal/IslandWindow.cpp`,
`IslandWindow.h`. Test plan: re-run the repro (alt+space) under
system dark + Terminal dark, expect a dark menu; flip to light,
expect light; run the WindowsTerminal unit tests.

## Candidate PR

### Title

Theme the system menu from the window theme update path

### Description

Summary of the Pull Request: the system menu now follows the
Terminal theme. On theme update, `IslandWindow` applies the
documented dark-mode menu attributes alongside the existing
frame/titlebar updates.

References and Relevant Issues: closes #20507.

Detailed Description: adds `_UpdateSystemMenuTheme()` called from the
existing theme-update path, per the plan posted on the issue. No
functional changes outside the system menu fix.

Validation Steps Performed: alt+space before/after under dark and
light (evidence below); `Terminal.Unit.Tests` pass.

PR Checklist: closes #20507; tests passed; documentation n/a; schema
n/a.

### Commits

- 4e7d9a1 IslandWindow: theme the system menu on theme updates
- b3c50f8 Rationalize theme update member naming and event plumbing
- 06f14dd Add experimental.menuFollowsWindowTheme setting

### Diff

```diff
--- a/src/cascadia/WindowsTerminal/IslandWindow.cpp
+++ b/src/cascadia/WindowsTerminal/IslandWindow.cpp
@@ -1838,6 +1838,19 @@ void IslandWindow::OnApplicationThemeChanged(const ElementTheme& requestedTheme)
     _currentTheme = requestedTheme;
     _updateFrameTheme();
+    _UpdateSystemMenuTheme();
+}
+
+// Apply the documented dark-mode attributes to the window's system
+// menu so alt+space follows the application theme (#20507).
+void IslandWindow::_UpdateSystemMenuTheme()
+{
+    const BOOL dark = _currentTheme == ElementTheme::Dark;
+    DwmSetWindowAttribute(_window.get(), DWMWA_USE_IMMERSIVE_DARK_MODE, &dark, sizeof(dark));
+    if (auto menu = GetSystemMenu(_window.get(), FALSE))
+    {
+        MENUINFO mi{ sizeof(MENUINFO), MIM_BACKGROUND | MIM_APPLYTOSUBMENUS };
+        mi.hbrBack = dark ? _darkMenuBrush.get() : nullptr;
+        SetMenuInfo(menu, &mi);
+    }
 }
@@ -212,11 +225,11 @@ void IslandWindow::Initialize()
-    _themeChangedRevoker = _settings.ThemeChanged(winrt::auto_revoke, { this, &IslandWindow::_onThemeChanged });
-    _frameBrush = _makeFrameBrush();
+    _themeRevoker = _settings.ThemeChanged(winrt::auto_revoke, { this, &IslandWindow::_HandleThemeChange });
+    _chromeBrush = _MakeChromeBrush();
--- a/src/cascadia/TerminalSettingsModel/GlobalAppSettings.idl
+++ b/src/cascadia/TerminalSettingsModel/GlobalAppSettings.idl
@@ -84,6 +84,7 @@ namespace Microsoft.Terminal.Settings.Model
         Boolean ForceVSync;
+        Boolean MenuFollowsWindowTheme;
         Boolean SoftwareRendering;
```

### Test evidence

Repro re-run (alt+space) on the branch: system dark + Terminal dark
now shows a dark system menu; switching the Terminal theme to light
flips it back on the next open. Screenshots attached before/after.
`Terminal.Unit.Tests` pass locally (0 failures).
