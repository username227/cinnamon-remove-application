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
    assert app.approve_packages(["test-package"]) is False
    assert seen == [{"mapped": True, "styled": False, "destructive": False}], seen

    # Exercise both palettes through the actual confirmation dialog.
    os.environ["CINNAMON_REMOVE_STYLE"] = "cinnamon"
    for scheme in ("light", "dark"):
        os.environ["CINNAMON_REMOVE_COLOR_SCHEME"] = scheme
        seen = capture_and_cancel()
        assert app.approve_packages(["test-package"]) is False
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
    assert app.approve_packages(["test-package"]) is False
    assert switched == [("before", "dark"), ("after", "light")], switched
    assert appearance._THEME_WATCHERS, "No system appearance signals connected"
    css = appearance._stylesheet("dark")
    assert "headerbar.titlebar" in css and "background-color: #242428" in css

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
    assert app.approve_packages(["test-package"]) is False
    assert seen == [{"mapped": True, "styled": False, "destructive": False}], seen

    # A CSS/theme exception must not stop the confirmation dialog from mapping.
    os.environ["CINNAMON_REMOVE_STYLE"] = "cinnamon"
    with mock.patch.object(appearance, "style_dialog", side_effect=RuntimeError("test failure")):
        seen = capture_and_cancel()
        assert app.approve_packages(["test-package"]) is False
        assert seen == [{"mapped": True, "styled": False, "destructive": False}], seen

    # Even in an error path, the message dialog must remain visible.
    os.environ["CINNAMON_REMOVE_COLOR_SCHEME"] = "dark"
    seen = capture_and_cancel()
    app.message("Safe smoke test")
    assert seen[0]["mapped"] and seen[0]["styled"], seen

print("GTK native/light/dark/fallback dialogs all mapped successfully")
