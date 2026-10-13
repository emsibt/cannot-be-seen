# Product

What cannot-be-seen does, how it behaves, and what it deliberately does not do.
`docs/ARCHITECTURE.md` covers how it is built; `AGENTS.md` covers the boundaries.

## The problem

You are sharing your screen in a Teams or Google Meet call and there is something
you need to look at that the room should not see - a personal message, a private
note, a second account.

## The one hard truth

Windows has exactly the right API for this:
`SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)`. A window with that
affinity stays fully visible on your monitor and is absent from every capture API
- the ones Teams and Meet read.

It only works on a window **the calling process owns**. For any other window
Windows returns `ERROR_ACCESS_DENIED`. This is not a permission that can be
acquired; it is an ownership check. `tools/probe_capture_exclusion.py`
demonstrates it on demand.

So the product is shaped by that: **the windows it can genuinely protect are the
ones it opens itself.** Everything else is a fallback, and the UI says so.

## Features

### 1. Protected windows - the real feature

A protected window is a Chromium (WebView2) window the app creates and owns, so
the OS accepts the exclusion call on it.

**Behaviour**

- Opened from the dashboard (label + URL) or the tray.
- Fully visible and fully interactive to the user: type, click, scroll normally.
- Absent from every screen capture - Teams, Meet, Zoom, `Win+Shift+S`.
- Carries a navigation bar: back, forward, reload, address field, new window,
  close. Keyboard: `Alt+←`/`Alt+→`, `F5`/`Ctrl+R`, `Ctrl+L`, `Ctrl+W`.
- The dashboard shows each one with its handle and claim status.
- Closing one removes it from the saved list.

**Logins persist.** The protected windows share a browser profile on disk, so
cookies, localStorage and sessions survive restarts. Sign in once, tick the
site's own "remember me", and you stay signed in.

**Limits, stated in the UI**

- It is not the user's Chrome: no shared logins, bookmarks or extensions.
- WebView2 does not expose Edge's password manager, so it will not offer to save
  passwords. Session persistence is the mechanism, not a saved password.
- The navigation bar is drawn over the page, covering roughly the top 38px.

**Acceptance**

- `tests/check_capture_exclusion.py` - a protected window reports affinity `0x11`.
- `tests/check_browser.py` - navigation bar injected, bridge wired, and exclusion
  lands on the protected window rather than another of ours opening at the same time.
- `tests/check_profile_persistence.py` - a cookie and a localStorage entry written
  by one process are read back by a second.

### 2. Dim - a reference overlay, not privacy

Makes another app's window translucent and click-through, so it can sit over the
shared screen as a faint reference without stealing clicks.

**Behaviour**

- **Click-through**: the mouse falls straight through to whatever is underneath.
- **Hold Ctrl** to interact with it again (click, scroll, select).
- **Transparency slider** on the dashboard, 0% (nearly solid) to 90% (barely
  there), applied live to every dimmed window and remembered between launches.
- Un-dim restores the window's opacity, mouse behaviour, and extended style
  exactly as they were.

**Not privacy.** Dimming changes how DWM composites the window onto the monitor;
it does not touch the capture stream. Participants still see it, fainter. This is
stated in the dashboard note, in the toast on dim, and asserted by a test.

**Acceptance**

- `tests/check_click_through.py` - `WindowFromPoint` falls through when dimmed,
  returns on Ctrl, alpha applies live and clamps, and affinity stays `WDA_NONE`.
- `tests/check_rules.py` - a manual dim survives the watcher; a rule-driven dim is
  released when its rule is switched off.

### 3. Pin - per window

**Pin** on any row raises that one window above everything else; **Unpin** puts it
back in the normal stack. Works on any window, foreign or protected.

Pinning is independent of dimming: dimming never changes it, so one dimmed window
can be pinned as a reference while another is dimmed and left in the stack.
Un-dimming leaves pinning exactly as it found it.

**Acceptance**

- `tests/check_click_through.py` - pinned stays pinned through dim, unpinned stays
  unpinned through dim, and both survive un-dimming.

### 4. Hide

Removes a window from the screen entirely. It is therefore absent from the share -
but the user cannot read it either. Offered for completeness, labelled honestly.

"Show all hidden" restores everything and switches off the rules that were holding
windows down, so they do not immediately disappear again.

### 5. Rules - re-applied automatically

A rule matches windows by app and/or title and is re-applied continuously, so a
window closed and reopened is covered again.

| Mode | Effect | Hides from a share? |
| --- | --- | --- |
| `dim` | Translucent and click-through | **No** - still captured, just fainter |
| `hide` | Removed from the screen | Yes, because it is not on screen at all |

**Nothing in this section hides a window from a share.** Rules are about
workflow. The dashboard says this in as many words.

Rules can be created from any row ("Always: this app" / "Always: this window"),
toggled, re-moded, and removed. "Show all hidden" disables the rules responsible.

### 6. Other screen - for real Chrome

When Teams or Meet shares "entire screen" it shares one monitor. Anything on a
display that is not being shared is never captured - no API tricks involved.

**Other screen** on any row moves that window to the other display in one click.
Rows show which display each window is on, and the dashboard reports how many
monitors were detected.

This is the route that works for the user's actual Chrome. It requires a second
monitor; without one the button is not shown.

**Acceptance**

- `tests/check_screens.py` - a window moves to the other display, its rect lands
  inside that display's bounds, and it returns. Skips itself on a single monitor.

### 7. Window tracking

The dashboard lists every visible, titled, non-cloaked top-level window with its
app, title, which screen it is on, and its state (`normal`, `dimmed · Ctrl to
use`, `pinned`, `hidden`, `excluded from capture`). Refreshes every 1.2s.

### 8. Tray

Icon (an eye with a slash) with: open dashboard, new protected window, show all
hidden, exclude dashboard from capture, quit. The dashboard itself is excluded
from capture by default - it lists the user's window titles - and that choice
persists.

### 9. Verification

- **Test in browser** opens `assets/verify.html`, which captures the screen with
  `getDisplayMedia` - the exact browser API Meet and Teams-on-web use - and shows
  the live capture next to a frozen snapshot. Put a protected window over the page:
  it stays on screen and is absent from the capture.
- `tools/probe_capture_exclusion.py` asks Windows directly whether a foreign
  window can be excluded, and prints the refusal.

## Non-goals

These are not "not yet". They are out of scope, and no amount of work changes it.

- **Hiding another app's window from a capture.** Blocked by Windows; see above.
  In particular, hiding the user's real Chrome window on the shared screen while
  keeping it readable is not achievable.
- **Injecting into another process** to work around that. Out of bounds - see
  `AGENTS.md` boundary 2.
- **Being a general-purpose browser.** Protected windows are for the private thing
  during a call, not a daily driver.
- **Working on macOS or Linux.** Win32, DWM and WebView2 only.
- **Hiding from a photograph of the screen.** Nothing can.

## Settings

`%LOCALAPPDATA%\cannot-be-seen\config.json`, edited through the dashboard:

| Setting | Default | Meaning |
| --- | --- | --- |
| `rules` | `[]` | Auto-applied dim/hide rules |
| `protected_tabs` | `[]` | Protected windows, reopened on launch |
| `dashboard_protected` | `true` | Exclude the dashboard itself from capture |
| `dim_alpha` | `140` | Dim opacity as an alpha value (slider shows the inverse) |
