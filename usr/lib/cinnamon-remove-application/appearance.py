"""Optional GTK 3 appearance layer for Cinnamon's uninstall dialogs.

The backend, widget construction, and window painting remain GTK-native.
This module must never prevent an uninstall confirmation from appearing.
"""
import configparser
import os
from pathlib import Path

from gi.repository import Gdk, Gio, Gtk


# Dark values approximate Cinnamon 6.8's own shell stylesheet. The light
# palette is deliberately neutral and works with light GTK themes.
_PALETTES = {
    "dark": {
        "surface": "#242428",
        "text": "#ffffff",
        "border": "#3b3b40",
        "button": "#39393c",
        "button_hover": "#49494e",
        "list": "#303034",
        "accent": "#3584e4",
        "danger": "#c01c28",
        "danger_hover": "#d12c37",
    },
    "light": {
        "surface": "#f2f2f4",
        "text": "#242428",
        "border": "#c4c4c9",
        "button": "#dedee2",
        "button_hover": "#ceced3",
        "list": "#ffffff",
        "accent": "#3584e4",
        "danger": "#c01c28",
        "danger_hover": "#d12c37",
    },
}

_PROVIDER = None
_CACHED_SCHEME = None


def _configuration():
    """Read optional per-user settings; missing/broken files are nonfatal."""
    parser = configparser.ConfigParser()
    path = Path(os.environ.get("XDG_CONFIG_HOME") or
                Path.home() / ".config") / "cinnamon-remove-application" / "settings.ini"
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error, ValueError):
        return {}
    if not parser.has_section("appearance"):
        return {}
    return dict(parser.items("appearance"))


def _setting(name, default):
    override = os.environ.get("CINNAMON_REMOVE_" + name.upper())
    if override is not None:
        return override.strip().lower()
    return _configuration().get(name.lower(), default).strip().lower()


def _settings(schema_name):
    try:
        source = Gio.SettingsSchemaSource.get_default()
        if source and source.lookup(schema_name, True):
            return Gio.Settings.new(schema_name)
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def _scheme():
    chosen = _setting("color_scheme", "system")
    if chosen in ("light", "dark"):
        return chosen

    # Cinnamon's Appearance > Dark mode selector: enum 0=no preference,
    # 1=prefer dark, 2=prefer light. Cinnamon 6.8 writes this value directly.
    try:
        portal = _settings("org.x.apps.portal")
        if portal is not None:
            mode = portal.get_enum("color-scheme")
            if mode == 1:
                return "dark"
            if mode == 2:
                return "light"
    except Exception:
        pass

    # Mixed/no-preference mode: prefer the active GTK theme, *not*
    # Cinnamon's independently selected St/shell theme.
    try:
        desktop = _settings("org.cinnamon.desktop.interface")
        if desktop is not None:
            name = desktop.get_string("gtk-theme")
        else:
            gtk_settings = Gtk.Settings.get_default()
            name = gtk_settings.get_property("gtk-theme-name") if gtk_settings else ""
        return "dark" if "dark" in (name or "").lower() else "light"
    except Exception:
        return "light"


def _stylesheet(scheme):
    return """
    .cinnamon-remove-dialog {
        background-color: %(surface)s;
        color: %(text)s;
    }
    .cinnamon-remove-dialog box,
    .cinnamon-remove-dialog .dialog-vbox,
    .cinnamon-remove-dialog .dialog-action-area {
        background-color: transparent;
    }
    .cinnamon-remove-dialog label {
        color: %(text)s;
    }
    .cinnamon-remove-dialog button {
        background-image: none;
        box-shadow: none;
        background-color: %(button)s;
        color: %(text)s;
        border: 1px solid %(border)s;
        border-radius: 10px;
        padding: 6px 16px;
        min-height: 30px;
        min-width: 100px;
        font-weight: bold;
    }
    .cinnamon-remove-dialog button:hover {
        background-color: %(button_hover)s;
    }
    .cinnamon-remove-dialog button.cinnamon-remove-destructive {
        background-color: %(danger)s;
        color: white;
        border-color: %(danger)s;
    }
    .cinnamon-remove-dialog button.cinnamon-remove-destructive:hover {
        background-color: %(danger_hover)s;
        border-color: %(danger_hover)s;
    }
    .cinnamon-remove-dialog scrolledwindow,
    .cinnamon-remove-dialog treeview.view {
        background-color: %(list)s;
        color: %(text)s;
    }
    .cinnamon-remove-dialog treeview.view:selected {
        background-color: %(accent)s;
        color: white;
    }
    """ % _PALETTES[scheme]


def style_dialog(dialog, destructive_response=None):
    """Apply a scoped stylesheet, never changing window decoration or painting.

    The caller catches failures and continues with unstyled native GTK dialogs.
    """
    global _PROVIDER, _CACHED_SCHEME
    if _setting("style", "cinnamon") in ("native", "gtk", "off", "0"):
        return False

    screen = dialog.get_screen() or Gdk.Screen.get_default()
    if screen is None:
        return False

    scheme = _scheme()
    if _PROVIDER is None:
        provider = Gtk.CssProvider()
        provider.load_from_data(_stylesheet(scheme).encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _PROVIDER = provider
        _CACHED_SCHEME = scheme
    elif scheme != _CACHED_SCHEME:
        # All dialogs are short-lived. This also supports manual theme changes
        # between dialogs if the module is reused in the same process.
        _PROVIDER.load_from_data(_stylesheet(scheme).encode("utf-8"))
        _CACHED_SCHEME = scheme

    dialog.get_style_context().add_class("cinnamon-remove-dialog")
    if destructive_response is not None:
        button = dialog.get_widget_for_response(destructive_response)
        if button is not None:
            button.get_style_context().add_class("cinnamon-remove-destructive")
    return True
