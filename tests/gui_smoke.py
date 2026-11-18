"""Headless GTK 3 regression smoke test: never invoke package removal."""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sys
import tempfile
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "usr/lib/cinnamon-remove-application"))
path = root / "usr/bin/cinnamon-remove-application"
loader = SourceFileLoader("cinnamon_remove_application", str(path))
spec = importlib.util.spec_from_loader("cinnamon_remove_application", loader)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

import appearance  # noqa: E402

assert Gtk.init_check()[0], "GTK could not connect to a display"


def capture_and_cancel(response=Gtk.ResponseType.CANCEL):
    """Capture the real displayed dialog and safely close it."""
    seen = []

    def cancel():
        for window in Gtk.Window.list_toplevels():
            if isinstance(window, Gtk.Dialog) and window.get_visible():
                assert not window.get_deletable(), "Redundant titlebar X still enabled"
                # Both cleanup checkboxes must start unchecked.
                checks = [child for child in window.get_content_area().get_children()
                          if isinstance(child, Gtk.CheckButton)]
                assert all(not check.get_active() for check in checks), (
                    "A cleanup checkbox was selected by default"
                )
                style = window.get_style_context()
                ok_button = window.get_widget_for_response(Gtk.ResponseType.OK)
                for button in window.get_action_area().get_children():
                    if isinstance(button, Gtk.Button) and style.has_class("cinnamon-remove-dialog"):
                        assert button.get_style_context().has_class("cinnamon-remove-action"), (
                            "Action button missing scoped styling class"
                        )
                seen.append({
                    "mapped": window.get_mapped(),
                    "styled": style.has_class("cinnamon-remove-dialog"),
                    "destructive": (
                        ok_button is not None and ok_button.get_style_context()
                        .has_class("cinnamon-remove-destructive")
                    ),
                })
                window.response(response)
                return False
        return True

    GLib.timeout_add(100, cancel)
    return seen


with tempfile.TemporaryDirectory() as config:
    # No user's actual configuration is read by the CI smoke test.
    os.environ["XDG_CONFIG_HOME"] = config

    # First verify the exact unstyled appearance we know works in Cinnamon.
    os.environ["CINNAMON_REMOVE_STYLE"] = "native"
    seen = capture_and_cancel()
    assert app.approve_packages(
        ["test-package"], cleanup_plan=lambda: ["test-package", "unused-dep"]) is None
    assert seen == [{"mapped": True, "styled": False, "destructive": False}], seen

    # Exercise both palettes through the actual confirmation dialog.
    os.environ["CINNAMON_REMOVE_STYLE"] = "cinnamon"
    for scheme in ("light", "dark"):
        os.environ["CINNAMON_REMOVE_COLOR_SCHEME"] = scheme
        seen = capture_and_cancel()
        assert app.approve_packages(
        ["test-package"], cleanup_plan=lambda: ["test-package", "unused-dep"]) is None
        assert seen == [{"mapped": True, "styled": True, "destructive": True}], seen
        assert appearance._PROVIDER is not None
        assert appearance._CACHED_SCHEME == scheme

    # Test a *live* change while the actual confirmation is mapped.
    # No package is removed: the dialog is always answered Cancel.
    os.environ["CINNAMON_REMOVE_COLOR_SCHEME"] = "dark"
    switched = []

    def switch_theme_during_dialog():
        dialogs = [win for win in Gtk.Window.list_toplevels()
                   if isinstance(win, Gtk.Dialog) and win.get_mapped()]
        if not dialogs:
            return True
        switched.append(("before", appearance._CACHED_SCHEME))
        os.environ["CINNAMON_REMOVE_COLOR_SCHEME"] = "light"
        # This is the same callback connected to Cinnamon's GSettings signal.
        appearance._refresh_theme()
        switched.append(("after", appearance._CACHED_SCHEME))
        dialogs[0].response(Gtk.ResponseType.CANCEL)
        return False

    GLib.timeout_add(100, switch_theme_during_dialog)
    assert app.approve_packages(
        ["test-package"], cleanup_plan=lambda: ["test-package", "unused-dep"]) is None
    assert switched == [("before", "dark"), ("after", "light")], switched
    assert appearance._THEME_WATCHERS, "No system appearance signals connected"
    css = appearance._stylesheet("dark")
    assert "headerbar.titlebar" in css and "background-color: #242428" in css
    # GTK3 column headers are buttons beneath the TreeView's 'header' CSS node.
    # Their backgrounds must follow the palette, not the (possibly light) GTK theme.
    for scheme, background in (("dark", "#39393c"), ("light", "#dedee2")):
        sheet = appearance._stylesheet(scheme)
        assert "treeview.view header button" in sheet
        assert "background-color: " + background in sheet
        assert "color: " + appearance._PALETTES[scheme]["text"] in sheet

    # Color scheme can come from Cinnamon's GSettings, not just an override.
    os.environ["CINNAMON_REMOVE_COLOR_SCHEME"] = "system"

    class PortalSettings:
        def __init__(self, value):
            self.value = value

        def get_enum(self, _key):
            return self.value

    with mock.patch.object(appearance, "_settings", return_value=PortalSettings(1)):
        assert appearance._scheme() == "dark"
    with mock.patch.object(appearance, "_settings", return_value=PortalSettings(2)):
        assert appearance._scheme() == "light"

    # The menu can use a persistent config file to opt out without a rebuild.
    config_file = Path(config) / "cinnamon-remove-application" / "settings.ini"
    config_file.parent.mkdir()
    config_file.write_text("[appearance]\nstyle = native\n", encoding="utf-8")
    os.environ.pop("CINNAMON_REMOVE_STYLE")
    seen = capture_and_cancel()
    assert app.approve_packages(
        ["test-package"], cleanup_plan=lambda: ["test-package", "unused-dep"]) is None
    assert seen == [{"mapped": True, "styled": False, "destructive": False}], seen

    # A CSS/theme exception must not stop the confirmation dialog from mapping.
    os.environ["CINNAMON_REMOVE_STYLE"] = "cinnamon"
    with mock.patch.object(appearance, "style_dialog", side_effect=RuntimeError("test failure")):
        seen = capture_and_cancel()
        assert app.approve_packages(
        ["test-package"], cleanup_plan=lambda: ["test-package", "unused-dep"]) is None
        assert seen == [{"mapped": True, "styled": False, "destructive": False}], seen

    # Even in an error path, the message dialog must remain visible.
    os.environ["CINNAMON_REMOVE_COLOR_SCHEME"] = "dark"
    seen = capture_and_cancel()
    app.message("Safe smoke test")
    assert seen[0]["mapped"] and seen[0]["styled"], seen

# Confirming the default pacman dialog must authorize the app only.
os.environ["CINNAMON_REMOVE_STYLE"] = "cinnamon"
os.environ["CINNAMON_REMOVE_COLOR_SCHEME"] = "dark"
capture_and_cancel(Gtk.ResponseType.OK)
assert app.approve_packages(
    ["test-package"], cleanup_plan=lambda: ["test-package", "unused-dep"]
) == ["test-package"]

# Opting in must update the exact visible package list before confirmation.
selection = []

def accept_pacman_dependencies():
    for window in Gtk.Window.list_toplevels():
        if not isinstance(window, Gtk.Dialog) or not window.get_mapped():
            continue
        children = window.get_content_area().get_children()
        checks = [w for w in children if isinstance(w, Gtk.CheckButton)]
        if not checks:
            continue
        check = checks[0]
        assert not check.get_active()
        check.set_active(True)
        scrolls = [w for w in children if isinstance(w, Gtk.ScrolledWindow)]
        assert len(scrolls) == 1
        view = scrolls[0].get_child()
        selection.extend(row[0] for row in view.get_model())
        window.response(Gtk.ResponseType.OK)
        return False
    return True

GLib.timeout_add(100, accept_pacman_dependencies)
assert app.approve_packages(
    ["test-package"], cleanup_plan=lambda: ["test-package", "unused-dep"]
) == ["test-package", "unused-dep"]
assert selection == ["test-package", "unused-dep"], selection

# A dangerous dependency preview must be rejected, without authorizing it.
with mock.patch.object(app, "message") as fake_warning:
    def reject_dangerous_plan():
        for window in Gtk.Window.list_toplevels():
            if not isinstance(window, Gtk.Dialog) or not window.get_mapped():
                continue
            checks = [w for w in window.get_content_area().get_children()
                      if isinstance(w, Gtk.CheckButton)]
            if not checks:
                continue
            checks[0].set_active(True)
            assert not checks[0].get_active()
            window.response(Gtk.ResponseType.CANCEL)
            return False
        return True
    GLib.timeout_add(100, reject_dangerous_plan)
    assert app.approve_packages(
        ["test-package"], cleanup_plan=lambda: ["test-package", "cinnamon"]
    ) is None
    assert fake_warning.call_count == 1

# Flatpak checkbox likewise begins unchecked; explicitly checking it is
# separately reflected in the approval result, without performing any removal.
flatpak_seen = capture_and_cancel()
assert app.approve_flatpak("org.example.App", "--user") == (False, False)
assert flatpak_seen and flatpak_seen[0]["mapped"]
checked_flatpak = []

def accept_flatpak_cleanup():
    for window in Gtk.Window.list_toplevels():
        if not isinstance(window, Gtk.Dialog) or not window.get_mapped():
            continue
        checks = [w for w in window.get_content_area().get_children()
                  if isinstance(w, Gtk.CheckButton)]
        if not checks:
            continue
        assert not checks[0].get_active()
        checks[0].set_active(True)
        checked_flatpak.append(checks[0].get_active())
        window.response(Gtk.ResponseType.OK)
        return False
    return True

GLib.timeout_add(100, accept_flatpak_cleanup)
assert app.approve_flatpak("org.example.App", "--user") == (True, True)
assert checked_flatpak == [True]

# Mock the full routing so that neither pacman nor Flatpak actually run.
with mock.patch.object(app, "validate_launcher", return_value="/fake.desktop"), \
     mock.patch.object(app, "package_owner", return_value=None), \
     mock.patch.object(app, "flatpak_target", return_value=("org.example.App", "--user")), \
     mock.patch.object(app, "perform", return_value=True) as perform_mock, \
     mock.patch.object(app, "approve_flatpak", return_value=(True, False)):
    assert app.main("/fake.desktop") == 0
    assert perform_mock.call_count == 1

with mock.patch.object(app, "validate_launcher", return_value="/fake.desktop"), \
     mock.patch.object(app, "package_owner", return_value=None), \
     mock.patch.object(app, "flatpak_target", return_value=("org.example.App", "--user")), \
     mock.patch.object(app, "perform", return_value=True) as perform_mock, \
     mock.patch.object(app, "approve_flatpak", return_value=(True, True)), \
     mock.patch.object(app, "message", return_value=Gtk.ResponseType.YES):
    assert app.main("/fake.desktop") == 0
    assert perform_mock.call_count == 2
    assert "--unused" not in perform_mock.call_args_list[0].args[0]
    assert "--unused" in perform_mock.call_args_list[1].args[0]

# A required pacman package must produce a helpful dependency explanation
# *without* opening an uninstall approval or starting any removal.
with mock.patch.object(app, "validate_launcher", return_value="/fake.desktop"), \
     mock.patch.object(app, "package_owner", return_value="shared-lib"), \
     mock.patch.object(app, "removal_plan", side_effect=app.RemovalError(
         "error: failed to prepare transaction (could not satisfy dependencies)")), \
     mock.patch.object(app, "required_by", return_value=["cinnamon", "player"]), \
     mock.patch.object(app, "approve_packages") as approval, \
     mock.patch.object(app, "perform") as removal, \
     mock.patch.object(app, "message") as warning:
    assert app.main("/fake.desktop") == 1
    assert warning.call_count == 1
    assert "shared-lib" in warning.call_args.args[0]
    assert "require" in warning.call_args.args[0]
    assert "cinnamon" in warning.call_args.kwargs["detail"]
    assert "player" in warning.call_args.kwargs["detail"]
    approval.assert_not_called()
    removal.assert_not_called()

# Even if direct dependents cannot be identified, show pacman's conflict as
# an understandable message rather than a generic top-level error.
with mock.patch.object(app, "required_by", return_value=[]), \
     mock.patch.object(app, "message") as warning:
    app.explain_pacman_preview_failure(
        "shared-lib", app.RemovalError(
            "error: failed to prepare transaction (could not satisfy dependencies)"))
    assert "breaking dependencies" in warning.call_args.args[0]
    assert "Nothing was removed" in warning.call_args.kwargs["detail"]

# Protected targets are rejected before pacman's dependency preview is called.
with mock.patch.object(app, "validate_launcher", return_value="/fake.desktop"), \
     mock.patch.object(app, "package_owner", return_value="cinnamon"), \
     mock.patch.object(app, "removal_plan") as preview, \
     mock.patch.object(app, "approve_packages") as approval, \
     mock.patch.object(app, "perform") as removal, \
     mock.patch.object(app, "message") as warning:
    assert app.main("/fake.desktop") == 1
    assert "protected system package" in warning.call_args.args[0]
    preview.assert_not_called()
    approval.assert_not_called()
    removal.assert_not_called()

# Ordinary leaf-package uninstall remains unchanged and exact.
with mock.patch.object(app, "validate_launcher", return_value="/fake.desktop"), \
     mock.patch.object(app, "package_owner", return_value="leaf-app"), \
     mock.patch.object(app, "removal_plan", return_value=["leaf-app"]) as preview, \
     mock.patch.object(app, "approve_packages", return_value=["leaf-app"]) as approval, \
     mock.patch.object(app, "perform", return_value=True) as removal:
    assert app.main("/fake.desktop") == 0
    preview.assert_called_once_with("leaf-app", include_unused=False)
    assert approval.call_count == 1
    assert removal.call_args.args[0][-1:] == ["leaf-app"]
    assert "-c" not in removal.call_args.args[0]

print("GTK native/light/dark/checkbox/dependency-block/fallback dialogs passed")
