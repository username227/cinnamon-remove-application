# Cinnamon Remove Application for Arch Linux

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

## Packaging and verification

**Initial release target: v1.0.0.** The root `PKGBUILD` remains a
Git-free release recipe, initially pinned to the existing `v0.1.6`
archive. The repository's `.gitattributes` marks `PKGBUILD export-ignore`:
the recipe stays on `master` but is excluded from GitHub's generated
source archives, preventing any circular source-checksum dependency.

**Release order:**

1. Tag the tested `master` commit `v1.0.0`.
2. Run `bash scripts/update-pkgbuild-release.sh 1.0.0` locally. This
   downloads the actual tagged GitHub archive, verifies its contents and
   calculates the SHA-256 checksum, then updates only `pkgver` and
   `sha256sums` in your local `PKGBUILD`.
3. Review the diff and test with `makepkg -Csi`.
4. Commit and push the tested `PKGBUILD` to `master` without moving
   the immutable tag; then publish the GitHub Release.

Until step 3, `makepkg -si` from the checked-in recipe builds `v0.1.6`.
Don't substitute `SKIP` for a checksum. The release tarball contains
application source; get the PKGBUILD from the repository.

For the non-destructive unit tests:

    python -m unittest discover -s tests -v

GitHub Actions also uses Xvfb to exercise the actual GTK dialogs, verify both
checkboxes default to unchecked, confirm that selecting pacman cleanup updates
the preview, check protected-package rejection, and verify the Flatpak cleanup
path with a mocked subprocess. **No real package is removed by the tests.**

The GTK appearance and both optional cleanup choices have been manually
exercised on Cinnamon 6.8 Wayland. A real pacman uninstall using a disposable
package is still recommended before publishing v1.0.0.

## Cinnamon-inspired dialogs

The interface keeps the original GTK dialog widgets and window decorations.
Its scoped GTK CSS changes colors, spacing, buttons,
and the package list and GTK titlebar, while respecting Cinnamon's portal light/dark preference
(`org.x.apps.portal color-scheme`) and using the active GTK theme as a
fallback. It does **not** replace the dialogs with Cinnamon shell code.

The color palette updates immediately when Cinnamon's portal light/dark
preference or GTK application theme changes, including while a dialog is open.
The default style is `cinnamon`. To disable it for one terminal invocation:

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
The CSS does not disable GTK's window painting, change the window visual, or
remove its decorations. Automated Xvfb tests check native, light, dark,
checkbox, and error-fallback dialogs; the interface has also been reviewed
in Cinnamon Wayland.

## Attribution and compatibility

Original Linux Mint application: Linux Mint team, mintcommon.
Original Arch adaptation: Giulio Girardi (rapgenic).
Manjaro's later Python 3 script: forum contributor stephan (stoffel).

License: GPL-2.0-or-later (inherited from Linux Mint's mintcommon).

