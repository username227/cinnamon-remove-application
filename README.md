# Cinnamon Remove Application - Arch Linux revival

Cinnamon 6.8 already provides its own Uninstall right-click menu item. The menu
checks for the executable at /usr/bin/cinnamon-remove-application and launches
it with the selected application's .desktop file path.

This independent Arch Linux / pacman adaptation preserves the native GTK 3
dialog flow with a Python 3 implementation. There are no Pamac dependencies.

## Design

- Determine the owning package with pacman -Qqo.
- Preview only the selected pacman package by default using
  `pacman -Rp --print-format %n`. Never use pacman's `-c` cascade option.
- Offer an **unchecked** "Also remove dependencies no longer required"
  checkbox. When selected, refresh the displayed removal list using
  `pacman -Rsp --print-format %n` before confirmation.
- Confirm the *complete* selected package set with a GTK 3 dialog, refuse
  protected packages, and remove only exactly those confirmed targets.
- Reject protected base and Cinnamon packages **before** invoking pacman's
  removal preview. If pacman rejects a removal because another installed
  package requires it, show that package's direct reverse dependents from
  `pacman -Qi` and explain that nothing was removed. No cascade is attempted.
- Authenticate via pkexec and remove *exactly* those approved packages with
  pacman -R --noconfirm. Pacman still checks dependency integrity.
- Recognize Flatpak-exported desktop launchers, if Flatpak is installed.
- Offer an **unchecked** Flatpak cleanup checkbox, allowing an additional
  `flatpak uninstall --unused` in the same user/system installation *after*
  successful application removal. Because Flatpak uninstall has no supported
  dry-run, show a **separate warning and confirmation** before any unused
  cleanup. This cleanup may include previously unused runtimes/extensions.
  Never pass `--delete-data`.
- Allow deletion of unowned launchers only from the normal applications folders.
- Display an error if polkit authentication is denied or removal fails.

Unlike the original 2018 Python 2 version, the frontend does not run as root.
Only the actual pacman subprocess is launched through pkexec.

## Package and tests

The root `PKGBUILD` is a **release recipe**, pinned to the existing
`v0.1.6` source tarball with its SHA-256 hash. It has **no git build
dependency**. Running `makepkg -si` builds that tagged release, **not**
the unreleased changes currently on this development branch. When the new
features are released, bump the version, tag the source, and calculate the
new tarball checksum rather than using a moving branch or bypassing integrity
verification.

For the non-destructive unit tests:

    python -m unittest discover -s tests -v

GitHub Actions also uses Xvfb to exercise the actual GTK dialogs, verify both
checkboxes default to unchecked, confirm that selecting pacman cleanup updates
the preview, check protected-package rejection, and verify the Flatpak cleanup
path with a mocked subprocess. **No real package is removed by the tests.**

Before releasing, test Cinnamon 6.8 Wayland with a disposable application,
review the displayed removal list, and click Cancel. Then verify each optional
cleanup choice separately with an expendable test package/Flatpak.

## Optional Cinnamon-inspired dialogs (experimental)

This *separate styling branch* keeps the original working GTK dialog widgets
and window decorations. Its scoped GTK CSS changes colors, spacing, buttons,
and the package list and GTK titlebar, while respecting Cinnamon's portal light/dark preference
(`org.x.apps.portal color-scheme`) and using the active GTK theme as a
fallback. It does **not** replace the dialogs with Cinnamon shell code.

The color palette updates immediately when Cinnamon's portal light/dark preference or GTK application theme changes, including while a dialog is open. The default in this branch is `cinnamon`. To disable it for one terminal
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
known-good `0.1.3-1`. The styling/cleanup work remains on the experimental branch
`feature/cinnamon-dialog-styling`; it is **not** part of the `v0.1.6` release.

## Attribution and compatibility

Original Linux Mint application: Linux Mint team, mintcommon.
Original Arch adaptation: Giulio Girardi (rapgenic).
Manjaro's later Python 3 script: forum contributor stephan (stoffel).

License: GPL-2.0-or-later (inherited from Linux Mint's mintcommon).

