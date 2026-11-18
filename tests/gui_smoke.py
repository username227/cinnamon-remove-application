"""Run only under Xvfb: smoke-test Cinnamon-like GTK dialogs without removing packages.

Verifies the same style initializer used by all confirmation/error dialogs.
"""
import importlib.util
from pathlib import Path
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "usr/lib/cinnamon-remove-application"))
spec = importlib.util.spec_from_file_location(
    "cinnamon_remove_application", root / "usr/bin/cinnamon-remove-application"
)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

assert Gtk.init_check()[0], "GTK could not connect to a display"
dlg = Gtk.MessageDialog(
    parent=None, flags=Gtk.DialogFlags.MODAL,
    message_type=Gtk.MessageType.WARNING,
    buttons=Gtk.ButtonsType.OK_CANCEL, text="Preview — nothing will be removed",
)
app._style_dialog(dlg, Gtk.ResponseType.OK)
dlg.show_all()
while Gtk.events_pending():
    Gtk.main_iteration()

assert dlg.get_visible(), "GTK confirmation dialog is not visible"
assert dlg.get_mapped(), "GTK confirmation dialog failed to map"
assert app._CSS_PROVIDER is not None, "Dialog stylesheet did not load"
assert not dlg.get_app_paintable(), "GTK automatic background painting disabled"
assert dlg.get_decorated(), "GTK window decorations unexpectedly disabled"
dlg.destroy()

# Also exercise the unowned/error-message initializer, without invoking pacman.
dlg = Gtk.MessageDialog(
    parent=None, flags=Gtk.DialogFlags.MODAL,
    message_type=Gtk.MessageType.ERROR,
    buttons=Gtk.ButtonsType.CLOSE, text="Safe smoke test",
)
app._style_dialog(dlg)
dlg.show_all()
while Gtk.events_pending():
    Gtk.main_iteration()
assert dlg.get_mapped()
dlg.destroy()
print("GTK dialog smoke test passed")

