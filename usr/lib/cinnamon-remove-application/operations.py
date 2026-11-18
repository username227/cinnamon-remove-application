"""Unprivileged pacman backend for the Cinnamon menu uninstall action.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import configparser
import os
from pathlib import Path
import re
import subprocess

PACMAN = "/usr/bin/pacman"
PKEXEC = "/usr/bin/pkexec"
FLATPAK = "/usr/bin/flatpak"
PACKAGE = re.compile(r"[A-Za-z0-9@._+\-]+\Z")
FLATPAK_ID = re.compile(r"[A-Za-z0-9._-]+\Z")

# Like Linux Mint, keep the application-menu uninstall action from removing
# fundamental desktop and system packages. Check *all* removal targets.
PROTECTED = frozenset({
    "base", "cinnamon", "cinnamon-control-center", "cinnamon-desktop",
    "cinnamon-menus", "cinnamon-session", "cinnamon-settings-daemon",
    "filesystem", "glibc", "muffin", "nemo", "pacman", "polkit", "systemd",
})


class RemovalError(Exception):
    """The requested removal cannot be planned safely."""


def run(args):
    try:
        return subprocess.run(args, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise RemovalError(str(exc)) from exc


def validate_launcher(path):
    result = Path(path).expanduser().absolute()
    if not result.is_file() or result.suffix != ".desktop":
        raise RemovalError("Not a valid desktop launcher: %s" % path)
    return str(result)


def package_owner(path):
    result = run([PACMAN, "-Qqo", "--", path])
    if result.returncode != 0:
        return None
    names = [name.strip() for name in result.stdout.splitlines() if name.strip()]
    if len(names) != 1 or not PACKAGE.fullmatch(names[0]):
        raise RemovalError("Could not identify the owning pacman package.")
    return names[0]


def removal_plan(package):
    if not PACKAGE.fullmatch(package):
        raise RemovalError("Invalid package name.")
    # Print, do not execute: -c includes reverse dependents and -s considers
    # newly unneeded dependencies, matching the previous Mint/Manjaro flow.
    result = run([PACMAN, "-Rcsp", "--print-format", "%n", "--", package])
    if result.returncode != 0:
        raise RemovalError(result.stderr.strip() or "Pacman removal preview failed.")
    names = list(dict.fromkeys(result.stdout.splitlines()))
    if not names or package not in names or any(not PACKAGE.fullmatch(name) for name in names):
        raise RemovalError("Pacman returned an invalid removal preview.")
    return [package] + [name for name in names if name != package]


def protected_in(packages):
    return sorted(set(packages).intersection(PROTECTED))


def removal_command(packages):
    if not packages or len(set(packages)) != len(packages):
        raise RemovalError("Empty or invalid removal plan.")
    if any(not PACKAGE.fullmatch(name) for name in packages):
        raise RemovalError("Invalid package name in removal plan.")
    blocked = protected_in(packages)
    if blocked:
        raise RemovalError("Protected packages: " + ", ".join(blocked))
    # Explicitly remove *only* the reviewed targets. Never add -c or -s to
    # the actual operation, which would risk growing the removal set.
    # Pacman still checks dependencies and aborts if the transaction changed.
    return [PKEXEC, PACMAN, "-R", "--noconfirm", "--noprogressbar", "--", *packages]


def flatpak_target(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        with open(path, encoding="utf-8") as stream:
            parser.read_file(stream)
        name = parser.get("Desktop Entry", "X-Flatpak", fallback="").strip()
    except (OSError, UnicodeError, configparser.Error):
        return None
    if not name or not FLATPAK_ID.fullmatch(name) or not os.path.isfile(FLATPAK):
        return None
    for scope in ("--user", "--system"):
        if run([FLATPAK, "info", scope, "--show-ref", name]).returncode == 0:
            return name, scope
    return None


def flatpak_removal_command(name, scope):
    if scope not in ("--user", "--system") or not FLATPAK_ID.fullmatch(name):
        raise RemovalError("Invalid Flatpak target.")
    # Flatpak performs its own polkit authentication for system installs.
    return [FLATPAK, "uninstall", scope, "--noninteractive", "--assumeyes", name]


def unowned_launcher_command(path):
    """Refuse arbitrary file deletion outside known application-menu paths."""
    resolved = Path(path).resolve(strict=True)
    user_data = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local/share"))
    if resolved.parent == (user_data / "applications").resolve():
        return ["/usr/bin/rm", "--", path]
    if resolved.parent in (Path("/usr/share/applications"), Path("/usr/local/share/applications")):
        return [PKEXEC, "/usr/bin/rm", "--", path]
    raise RemovalError("Refusing to delete a launcher outside standard applications folders.")

