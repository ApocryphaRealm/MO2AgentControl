r"""MO2 Agent Control - its button in MO2's tool bar (Qt only, no mobase, so the tests run this very code without MO2).

The button opens the plugin's status window, the same one Tools -> MO2 Agent Control opens. It FOLLOWS THE THEME: the
PNG beside this file is only the shape; its alpha is filled with the colour MO2's current stylesheet gives a tool bar
button (the palette Qt resolves on polish - button text, else window text) and repainted whenever that colour changes.
A timer looks every two seconds, so a theme switch, an edited .qss or MO2 rebuilding its tool bar all reach it. The
timer belongs to this object, never to one of MO2's widgets, and nothing of MO2's is subclassed or filtered.
"""
import os

try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPalette, QPixmap
    from PyQt6.QtWidgets import QApplication, QToolBar, QToolButton
except ImportError:  # MO2 before 2.5
    from PyQt5.QtCore import QTimer
    from PyQt5.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
    from PyQt5.QtWidgets import QAction, QApplication, QToolBar, QToolButton

ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-control.png")
ACTION_NAME = "MO2AgentControlAction"
BUTTON_NAME = "MO2AgentControlBtn"


def _role(name):
    return getattr(getattr(QPalette, "ColorRole", QPalette), name)


def themed_icon(colour, path=ICON):
    """The shape of the PNG, filled with `colour`."""
    src = QPixmap(path)
    if src.isNull():
        return QIcon()
    out = QPixmap(src.size())
    out.fill(QColor(0, 0, 0, 0))
    p = QPainter(out)
    p.drawPixmap(0, 0, src)
    mode = getattr(QPainter, "CompositionMode", QPainter)
    p.setCompositionMode(mode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), colour)
    p.end()
    return QIcon(out)


def button_colour(widget):
    """The colour the stylesheet in force gives this widget's text: QPalette.ColorRole.ButtonText, else WindowText."""
    widget.ensurePolished()
    pal = widget.palette()
    c = pal.color(_role("ButtonText"))
    if not c.isValid() or c.alpha() == 0:
        c = pal.color(_role("WindowText"))
    return c


def _colour_key(c):
    fmt = getattr(QColor, "NameFormat", QColor)
    return c.name(fmt.HexArgb)


def menu_icon():
    """For MO2's Tools menu entry: the application's text colour at the moment MO2 asks."""
    app = QApplication.instance()
    if app is None:
        return QIcon()
    return themed_icon(app.palette().color(_role("WindowText")))


def main_window():
    app = QApplication.instance()
    if app is None:
        return None
    tops = app.topLevelWidgets()
    for w in tops:
        if w.metaObject().className() == "MainWindow" or w.objectName() == "MainWindow":
            return w
    for w in tops:
        if w.isVisible() and w.findChild(QToolBar) is not None:
            return w
    return None


class ToolbarButton:
    """text(), tooltip(): callables (the language can change); trigger: what a press does; log(line)."""

    def __init__(self, text, tooltip, trigger, log=lambda s: None):
        self._text, self._tooltip, self._trigger, self._log = text, tooltip, trigger, log
        self._action = None
        self._colour = None
        self._timer = QTimer()                  # owned here, not by an MO2 widget
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.keep)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def keep(self):
        """Put the button in the tool bar if it is not there (MO2 rebuilds its tool bar), and keep its colour right."""
        try:
            window = main_window()
            if window is None:
                return
            bars = window.findChildren(QToolBar)
            if not bars:
                return
            tb = bars[0]
            if self._action is not None and self._action in tb.actions():
                self._timer.setInterval(2000)   # in place: just keep an eye on it
                self._tint(tb)
                return
            act = QAction(QIcon(), self._text(), window)
            act.setObjectName(ACTION_NAME)
            act.setToolTip(self._tooltip())
            act.triggered.connect(lambda _checked=False: self._trigger())
            anchor = None
            for a in tb.actions():      # beside the other tools, before Settings where MO2 has one
                label = (a.text() or "").replace("&", "").lower()
                if "settings" in label or "settings" in (a.toolTip() or "").lower():
                    anchor = a
                    break
            if anchor is not None:
                tb.insertAction(anchor, act)
            else:
                tb.addAction(act)
            btn = tb.widgetForAction(act)
            if isinstance(btn, QToolButton):
                btn.setObjectName(BUTTON_NAME)
                btn.setAutoRaise(True)
                btn.setIconSize(tb.iconSize())
            self._action = act
            self._colour = None
            self._tint(tb)
            self._log("toolbar button added")
        except Exception as exc:  # noqa: BLE001
            self._log("toolbar button: %r" % (exc,))

    def _tint(self, tb):
        btn = tb.widgetForAction(self._action) if self._action is not None else None
        if btn is None:
            return
        c = button_colour(btn)
        key = _colour_key(c)
        if key == self._colour:
            return
        self._action.setIcon(themed_icon(c))
        self._colour = key
        self._log("toolbar icon painted in %s (the theme's button colour)" % key)
