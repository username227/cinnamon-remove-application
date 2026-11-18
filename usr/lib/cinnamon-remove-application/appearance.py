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
_THEME_WATCHERS = []


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
    /* GTK3 creates a separate client-side headerbar. Style it with the
       same palette as the body; don't change decorations or window painting. */
    .cinnamon-remove-dialog headerbar,
    .cinnamon-remove-dialog headerbar.titlebar {
        background-image: none;
        background-color: %(surface)s;
        color: %(text)s;
        border-color: %(border)s;
        box-shadow: none;
    }
    .cinnamon-remove-dialog headerbar label,
    .cinnamon-remove-dialog headerbar.titlebar label {
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
    /* Style action buttons only. Styling all buttons accidentally enlarged
       the titlebar's window-close button under Cinnamon/Wayland. */
    .cinnamon-remove-dialog button.cinnamon-remove-action {
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
    .cinnamon-remove-dialog button.cinnamon-remove-action:hover {
        background-color: %(button_hover)s;
    }
    .cinnamon-remove-dialog button.cinnamon-remove-action.cinnamon-remove-destructive {
        background-color: %(danger)s;
        color: white;
        border-color: %(danger)s;
    }
    .cinnamon-remove-dialog button.cinnamon-remove-action.cinnamon-remove-destructive:hover {
        background-color: %(danger_hover)s;
        border-color: %(danger_hover)s;
    }
    /* GTK theme label rules otherwise override the destructive foreground. */
    .cinnamon-remove-dialog button.cinnamon-remove-destructive label {
        color: white;
    }
    /* GTK themes can paint column-header buttons light even when the
       TreeView is dark. Recolor the header *background*, preserving the
       existing high-contrast text color. */
    .cinnamon-remove-dialog treeview.view header button,
    .cinnamon-remove-dialog treeview.view header button:hover,
    .cinnamon-remove-dialog treeview.view header button:active,
    .cinnamon-remove-dialog treeview.view header button:backdrop {
        background-image: none;
        background-color: %(button)s;
        box-shadow: none;
        border-color: %(border)s;
        color: %(text)s;
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


def _refresh_theme(*_unused):
    """Recolor already-open dialogs when Cinnamon's settings change."""
    global _CACHED_SCHEME
    if _PROVIDER is None:
        return
    try:
        scheme = _scheme()
        if scheme != _CACHED_SCHEME:
            _PROVIDER.load_from_data(_stylesheet(scheme).encode("utf-8"))
            _CACHED_SCHEME = scheme
    except Exception as exc:
        # Theme events must never interfere with an uninstall confirmation.
        import sys
        print("cinnamon-remove-application: could not refresh theme: "
              + str(exc), file=sys.stderr)


def _watch_system_appearance():
    """Track Cinnamon's portal preference and GTK application-theme changes."""
    for schema, key in (
        ("org.x.apps.portal", "color-scheme"),
        ("org.cinnamon.desktop.interface", "gtk-theme"),
    ):
        try:
            settings = _settings(schema)
            if settings is not None:
                signal_id = settings.connect("changed::" + key, _refresh_theme)
                _THEME_WATCHERS.append((settings, signal_id))
        except Exception:
            # Missing or incompatible schemas should not affect dialogs.
            continue
    try:
        gtk_settings = Gtk.Settings.get_default()
        if gtk_settings is not None:
            signal_id = gtk_settings.connect(
                "notify::gtk-theme-name", _refresh_theme)
            _THEME_WATCHERS.append((gtk_settings, signal_id))
    except Exception:
        pass


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
        _watch_system_appearance()
    elif scheme != _CACHED_SCHEME:
        _refresh_theme()

    dialog.get_style_context().add_class("cinnamon-remove-dialog")
    # Restrict rounded, wide button styling to dialog actions, not headerbar
    # controls (the latter were stretched by the previous broad CSS selector).
    for button in dialog.get_action_area().get_children():
        if isinstance(button, Gtk.Button):
            button.get_style_context().add_class("cinnamon-remove-action")
    if destructive_response is not None:
        button = dialog.get_widget_for_response(destructive_response)
        if button is not None:
            button.get_style_context().add_class("cinnamon-remove-destructive")
    return True
