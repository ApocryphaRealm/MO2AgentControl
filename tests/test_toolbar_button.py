r"""The plugin's tool bar button (plugins\ApocryphaAgentControl\toolbar.py) on a stand-in for MO2's main window - a
QMainWindow named "MainWindow" with a tool bar that has a Settings entry. Qt's offscreen platform, no MO2.

  python tests\test_toolbar_button.py

  1  the button is added before Settings, with its object names, its text and tooltip, and a real icon
  2  it is painted in the colour the stylesheet gives a tool bar button, and repainted when the stylesheet changes
  3  a press calls the plugin's own display; the button comes back when the tool bar is rebuilt; no second button is added
  4  the window commands see it: ui_tree lists the button by its objectName, ui_menus lists the entry
"""
import importlib.util
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QColor  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow, QToolBar  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(REPO, "plugins", "ApocryphaAgentControl")


def load(name):
    spec = importlib.util.spec_from_file_location("ac_" + name, os.path.join(PLUGIN, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


toolbar, ui = load("toolbar"), load("ui")
n = 0


def ok(cond, what, detail=""):
    global n
    n += 1
    print(("PASS" if cond else "FAIL"), n, what)
    if not cond:
        print(detail)
        sys.exit(1)


def icon_colour(action):
    """The colour of the most opaque pixel of the action's icon."""
    img = action.icon().pixmap(64, 64).toImage()
    best = None
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = QColor.fromRgba(img.pixel(x, y))
            if best is None or c.alpha() > best.alpha():
                best = c
    return best


app = QApplication(sys.argv[:1])
win = QMainWindow()
win.setObjectName("MainWindow")
win.setWindowTitle("Stand-in MO2")
tb = QToolBar()
win.addToolBar(tb)
tb.addAction("Install Mod")
settings = tb.addAction("Settings")
tb.addAction("Help")
app.setStyleSheet("QToolButton { color: #f5f2e9; }")
win.show()

pressed, logged = [], []
button = toolbar.ToolbarButton(lambda: "MO2 Agent Control", lambda: "Shows whether the command channel is listening",
                               lambda: pressed.append(1), logged.append)
button.keep()
acts = tb.actions()
ours = [a for a in acts if a.objectName() == toolbar.ACTION_NAME]
ok(len(ours) == 1 and acts.index(ours[0]) == acts.index(settings) - 1, "the button is in the tool bar, just before Settings",
   [a.text() for a in acts])
act = ours[0]
btn = tb.widgetForAction(act)
ok(act.text() == "MO2 Agent Control" and "listening" in act.toolTip() and btn.objectName() == toolbar.BUTTON_NAME,
   "it carries the product name, the tooltip and its object names")
ok(os.path.isfile(toolbar.ICON) and not act.icon().isNull(), "it has an icon, from the PNG beside the plugin", toolbar.ICON)
c = icon_colour(act)
ok((c.red(), c.green(), c.blue()) == (0xf5, 0xf2, 0xe9) and c.alpha() > 200, "the icon is painted in the stylesheet's button colour",
   c.name())
ok(any("painted in" in x for x in logged), "... and the log says which colour", logged)

app.setStyleSheet("QToolButton { color: #203040; }")
button.keep()
c = icon_colour(act)
ok((c.red(), c.green(), c.blue()) == (0x20, 0x30, 0x40), "a changed stylesheet repaints it at the next look", c.name())
before = len(logged)
button.keep()
ok(len(logged) == before and len([a for a in tb.actions() if a.objectName() == toolbar.ACTION_NAME]) == 1,
   "an unchanged theme repaints nothing, and no second button is added")

act.trigger()
ok(pressed == [1], "a press opens the plugin's own window (its display)")
tb.removeAction(act)
button.keep()
again = [a for a in tb.actions() if a.objectName() == toolbar.ACTION_NAME]
ok(len(again) == 1 and not again[0].icon().isNull(), "after the tool bar is rebuilt the button comes back, painted")

app.processEvents()      # the re-added button is shown at the next turn of the event loop
r = ui.tree({"window": "MainWindow", "kinds": ["button"]})
ok(any(x["name"] == toolbar.BUTTON_NAME and x["text"] == "MO2 Agent Control" for x in r["controls"]),
   "ui_tree lists it as a button with its objectName", [(x["name"], x.get("text")) for x in r["controls"]])
r = ui.menus({"window": "MainWindow"})
ok(any(e["path"] == "MO2 Agent Control" and e.get("name") == toolbar.ACTION_NAME for e in r["entries"]),
   "ui_menus lists the entry", r["entries"])
ok(not toolbar.menu_icon().isNull(), "the Tools menu entry has an icon too")
print("ALL PASS", n)
