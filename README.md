# Cinnamon Remove Application - Arch Linux revival

Cinnamon 6.8 already provides its own Uninstall right-click menu item. The menu
checks for the executable at /usr/bin/cinnamon-remove-application and launches
it with the selected application's .desktop file path.

This independent Arch Linux / pacman adaptation preserves the native GTK 3
dialog flow with a Python 3 implementation. There are no Pamac dependencies.

## Design

- Determine the owning package with pacman -Qqo.
- Preview the full reverse-dependent and unused-dependency removal plan with
  pacman -Rcsp --print-format %n (a non-destructive operation).
- Confirm the *complete* set of packages with a GTK 3 dialog.
- Refuse to proceed if the plan includes protected base or Cinnamon packages.
- Authenticate via pkexec and remove *exactly* those approved packages with
  pacman -R --noconfirm. Pacman still checks dependency integrity.
- Recognize Flatpak-exported desktop launchers, if Flatpak is installed.
- Allow deletion of unowned launchers only from the normal applications folders.
- Display an error if polkit authentication is denied or removal fails.

Unlike the original 2018 Python 2 version, the frontend does not run as root.
Only the actual pacman subprocess is launched through pkexec.

## Install for testing

From a checkout of this development branch, run:

    makepkg -si

The PKGBUILD is a development recipe and fetches this branch, not a release
tag. No existing Cinnamon applet needs to be patched or configured. Logging
out and back in may be needed for the menu to detect the new executable.

For non-destructive unit tests:

    python -m unittest discover -s tests -v

Manual testing with Cinnamon 6.8 and a disposable leaf package is still needed.
First confirm the displayed packages match pacman's dry-run results and cancel
the transaction. Proceed with real uninstall tests only after review.

## Optional Cinnamon-inspired dialogs (experimental)

This *separate styling branch* keeps the original working GTK dialog widgets
and window decorations. Its scoped GTK CSS changes colors, spacing, buttons,
and the package list, while respecting Cinnamon's portal light/dark preference
(`org.x.apps.portal color-scheme`) and using the active GTK theme as a
fallback. It does **not** replace the dialogs with Cinnamon shell code.

The default in this branch is `cinnamon`. To disable it for one terminal
invocation:

    CINNAMON_REMOVE_STYLE=native /usr/bin/cinnamon-remove-application /usr/share/applications/your-app.desktop

To disable styling for the menu's Uninstall action *without reinstalling*,
create `~/.config/cinnamon-remove-application/settings.ini`:

    [appearance]
    style = native

The available values are `cinnamon` (default) and `native`. Optionally set
`color_scheme = system`, `light`, or `dark` under `[appearance]` to override
the system-detected palette. Environment variables
`CINNAMON_REMOVE_STYLE` and `CINNAMON_REMOVE_COLOR_SCHEME` take precedence.

A styling exception logs a warning to stderr and falls back to native GTK.
This experimental CSS does not disable GTK's own window painting, change the
window visual, or remove its decorations. Automated Xvfb tests check that
native, light, dark, and error-fallback dialogs map; **manual Cinnamon Wayland
testing is still required**.

The stable development branch `modernize/cinnamon-6.8-pacman` remains at the
known-good `0.1.3-1`. The experimental PKGBUILD fetches only
`feature/cinnamon-dialog-styling` as `0.1.4-1`.

## Attribution and compatibility

Original Linux Mint application: Linux Mint team, mintcommon.
Original Arch adaptation: Giulio Girardi (rapgenic).
Manjaro's later Python 3 script: forum contributor stephan (stoffel).

License: GPL-2.0-or-later (inherited from Linux Mint's mintcommon).

