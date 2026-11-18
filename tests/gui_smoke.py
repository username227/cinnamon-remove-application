"""Run only under Xvfb: smoke-test Cinnamon-like GTK dialogs without removing packages.

Verifies the same style initializer used by all confirmation/error dialogs.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "usr/lib/cinnamon-remove-application"))
path = root / "usr/bin/cinnamon-remove-application"
loader = SourceFileLoader("cinnamon_remove_application", str(path))
spec = importlib.util.spec_from_loader("cinnamon_remove_application", loader)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

assert Gtk.init_check()[0], "GTK could not connect to a display"
dlg = Gtk.MessageDialog(
    parent=None, flags=Gtk.DialogFlags.MODAL,
    message_type=Gtk.MessageType.WARNING,
    buttons=Gtk.ButtonsType.OK_CANCEL, text="Preview — nothing will be removed",
)
# Exercise the *actual* confirmation function without authorizing removal.
# The timeout sees the dialog after it maps and responds Cancel.
seen = []
def cancel_dialog():
    for window in Gtk.Window.list_toplevels():
        if isinstance(window, Gtk.Dialog) and window.get_visible():
            seen.append(window.get_mapped())
            window.response(Gtk.ResponseType.CANCEL)
            return False
    return True

from gi.repository import GLib
dlg.destroy()
GLib.timeout_add(100, cancel_dialog)
assert app.approve_packages(["test-package"]) is False
assert seen == [True], "Package confirmation was not mapped"

# The error-message path uses the same native GTK dialog machinery.
seen.clear()
GLib.timeout_add(100, cancel_dialog)
app.message("Safe smoke test")
assert seen == [True], "Error dialog was not mapped"
print("GTK confirmation and error dialogs mapped successfully")

