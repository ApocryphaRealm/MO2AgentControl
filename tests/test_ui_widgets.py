r"""The window commands (ui_tree, ui_click, ui_answer_modal, ui_set) against real Qt widgets, through the plugin's own
socket code (channel.py), command core (core.py) and widget code (ui.py) - no MO2. Needs PyQt6 (pip install PyQt6);
Qt's "offscreen" platform is used, so no window appears on the screen.

  python tests\test_ui_widgets.py

  1  THE KEY QUESTION: while a modal dialog's exec() is open (a nested event loop on the GUI thread), a request on the
     channel is still answered - ui_tree describes the open dialog, ui_answer_modal closes it
  2  ui_tree: the windows, the controls with objectName / text / enabled / value, a label's text as an edit's text
  3  ui_click: a plain button; a button that OPENS a modal replies "returned": false with the dialog described instead
     of hanging; the dialog is then answered by text (two buttons share the accept role, so role alone is refused) and
     by role; nothing behind an open modal can be acted on
  4  ui_set: checkbox, edit, combo (by text and by index), spin box, tab bar - each read back; wrong types refused
  7  lists, tables and trees (ui_items, ui_item) and  8  menus and tool bars (ui_menus, ui_menu)
  6  a dialog inside a dialog: a tool window run with exec() and a question asked from inside it
  5  safety: an ambiguous locator is refused with the candidates listed, path and index pick one; a disabled button is
     refused; a write while MO2 is in use is refused without confirm; a click backs the profile's lists up first
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import mo2_ctl  # noqa: E402

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal  # noqa: E402
from PyQt6.QtGui import QStandardItem, QStandardItemModel  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QListWidget, QMenuBar, QToolBar,  # noqa: E402
                             QTreeView, QGroupBox, QLabel, QLineEdit,  # noqa: E402
                             QMessageBox, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

PLUGIN = os.path.join(REPO, "plugins", "ApocryphaAgentControl")


def load(name):
    spec = importlib.util.spec_from_file_location("ac_" + name, os.path.join(PLUGIN, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core, channel, ui = load("core"), load("channel"), load("ui")
T = os.path.join(tempfile.gettempdir(), "mo2-agent-control-ui-test")
shutil.rmtree(T, ignore_errors=True)
os.makedirs(os.path.join(T, "profile"))
for f in core.PROFILE_FILES:
    open(os.path.join(T, "profile", f), "w").write(f + "\n")


class Org:
    """Only what these commands need of the adapter: the profile folder (for the backup) and the four ui methods,
    which the plugin's own adapter hands to ui.py in exactly this way."""
    def profile_dir(self): return os.path.join(T, "profile")
    def ui_tree(self, a): return ui.tree(a)
    def ui_click(self, a): return ui.click(a)
    def ui_answer_modal(self, a): return ui.answer_modal(a)
    def ui_set(self, a): return ui.set_value(a)
    def ui_items(self, a): return ui.items(a)
    def ui_item(self, a): return ui.item(a)
    def ui_menus(self, a): return ui.menus(a)
    def ui_menu(self, a): return ui.menu(a)


app = QApplication(sys.argv[:1])
seen = {"ping": 0, "apply": [], "ask": [], "edited": 0, "activated": []}

win = QWidget()
win.setObjectName("testWin")
win.setWindowTitle("Test Window")
lay = QVBoxLayout(win)
ping = QPushButton("&Ping")
ping.setObjectName("pingBtn")
ping.clicked.connect(lambda: seen.__setitem__("ping", seen["ping"] + 1))
apply_btn = QPushButton("&Apply")
apply_btn.setObjectName("applyBtn")
ask_btn = QPushButton("Ask")
dead = QPushButton("Dead")
dead.setEnabled(False)
lay.addWidget(ping), lay.addWidget(apply_btn), lay.addWidget(ask_btn), lay.addWidget(dead)
for side in ("Left", "Right"):
    g = QGroupBox(side)
    gl = QVBoxLayout(g)
    b = QPushButton("Same")
    b.clicked.connect(lambda _=False, side=side: seen.setdefault("same", []).append(side))
    gl.addWidget(b)
    lay.addWidget(g)
form = QFormLayout()
check = QCheckBox("Enable thing")
edit = QLineEdit()
edit.setObjectName("nameEdit")
edit.textEdited.connect(lambda _t: seen.__setitem__("edited", seen["edited"] + 1))
name_label = QLabel("&Name:")
name_label.setBuddy(edit)
combo = QComboBox()
combo.setObjectName("modeCombo")
combo.addItems(["Fast", "Careful", "Off"])
combo.activated.connect(lambda i: seen["activated"].append(i))
spin = QSpinBox()
spin.setObjectName("countSpin")
spin.setRange(0, 10)
form.addRow(check), form.addRow(name_label, edit), form.addRow("Mode", combo), form.addRow("Count", spin)
lay.addLayout(form)
tabs = QTabWidget()
tabs.setObjectName("pages")
tabs.addTab(QWidget(), "One"), tabs.addTab(QWidget(), "Two")
lay.addWidget(tabs)


def do_apply():
    """The shape of MO2 Modlist Manager's Apply question: two buttons with the accept role, and Cancel."""
    box = QMessageBox(win)
    box.setWindowTitle("Apply")
    box.setText("3 plugins would lose a master.")
    b_all = box.addButton("Apply and switch them off", QMessageBox.ButtonRole.AcceptRole)
    b_keep = box.addButton("Apply, leave plugins as they are", QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    hit = box.clickedButton()
    seen["apply"].append("all" if hit is b_all else "keep" if hit is b_keep else "cancel")


def do_ask():
    r = QMessageBox.question(win, "Restore backup", "Restore the backup from 12:00?")
    seen["ask"].append("yes" if r == QMessageBox.StandardButton.Yes else "no")


def do_tool():
    """The shape of a plugin tool's window: a dialog run with exec(), holding a button that asks a question."""
    dlg = QDialog(win)
    dlg.setWindowTitle("Tool")
    dl = QVBoxLayout(dlg)
    go, close = QPushButton("Go"), QPushButton("Close")
    go.clicked.connect(lambda: seen.setdefault("go", []).append(
        QMessageBox.question(dlg, "Sure?", "Do it?") == QMessageBox.StandardButton.Yes))
    close.clicked.connect(dlg.accept)
    dl.addWidget(go), dl.addWidget(close)
    dlg.exec()
    seen["tool_closed"] = True


tool_btn = QPushButton("Open tool")
tool_btn.setObjectName("toolBtn")
tool_btn.clicked.connect(do_tool)
lay.addWidget(tool_btn)

# ---- a tree with tick boxes (the shape of MO2's mod list), a plain list, a menu bar and a tool bar
tree_view = QTreeView()
tree_view.setObjectName("modTree")
model = QStandardItemModel()
model.setHorizontalHeaderLabels(["Mod", "Priority"])
for i, (label, ticked) in enumerate((("Alpha", True), ("Bravo", False), ("Same", False), ("Same", True))):
    it = QStandardItem(label)
    it.setCheckable(True)
    it.setCheckState(Qt.CheckState.Checked if ticked else Qt.CheckState.Unchecked)
    model.appendRow([it, QStandardItem(str(i))])
folder = QStandardItem("Folder")
for child in ("one.esp", "two.esp"):
    folder.appendRow([QStandardItem(child), QStandardItem("")])
model.appendRow([folder, QStandardItem("4")])
forced = QStandardItem("Forced")           # a box that is shown but not the person's to tick (a game's own master)
forced.setCheckState(Qt.CheckState.Checked)
model.appendRow([forced, QStandardItem("9")])
locked = QStandardItem("Locked")
locked.setCheckable(True)
locked.setEnabled(False)
model.appendRow([locked, QStandardItem("5")])
tree_view.setModel(model)
model.itemChanged.connect(lambda it: seen.setdefault("ticked", []).append((it.text(), it.checkState() == Qt.CheckState.Checked)))
plain_list = QListWidget()
plain_list.addItems(["red", "green", "blue"])
lay.addWidget(tree_view), lay.addWidget(plain_list)
bar = QMenuBar()
m_file = bar.addMenu("&File")
m_file.addAction("&Open...\tCtrl+O").triggered.connect(lambda: seen.setdefault("menu", []).append("open"))
m_recent = m_file.addMenu("&Recent")
m_recent.addAction("first.txt").triggered.connect(lambda: seen.setdefault("menu", []).append("recent-first"))
gone = m_file.addAction("Gone")
gone.setEnabled(False)
m_view = bar.addMenu("&View")
wrap = m_view.addAction("Word wrap")
wrap.setCheckable(True)
m_tools = bar.addMenu("&Tools")
m_tools.addAction("Ask...").triggered.connect(do_ask)
tb = QToolBar()
act_refresh = tb.addAction("Refresh")
act_refresh.setObjectName("actionRefresh")
act_refresh.triggered.connect(lambda: seen.setdefault("menu", []).append("refresh"))
lay.setMenuBar(bar)
lay.addWidget(tb)

apply_btn.clicked.connect(do_apply)
ask_btn.clicked.connect(do_ask)
win.show()

busy = {"v": False}
logged = []
disp = core.Dispatcher(Org(), "tok", os.path.join(T, "backups"), lambda: (busy["v"], "MO2 is in front and in use"),
                       logged.append, "test")
chan = channel.Channel(disp, logged.append)
PORT = chan.listen()
assert PORT, chan.error()
CH = {"port": PORT, "token": "tok"}
n = 0
failed = []


def req(cmd, timeout=10, confirm="", **args):
    r = {"token": "tok", "cmd": cmd, "args": args}
    if confirm:
        r["confirm"] = confirm
    return mo2_ctl.send(CH, r, timeout)


def ok(cond, what, detail=""):
    global n
    n += 1
    print(("PASS" if cond else "FAIL"), n, what, flush=True)
    if not cond:
        print(detail, flush=True)
        failed.append(what)
        raise SystemExit(1)


class Bridge(QObject):
    call = pyqtSignal(object)


bridge = Bridge()
bridge.call.connect(lambda fn: fn())     # connected on the GUI thread, so an emit from the test thread is queued to it


def on_gui(fn):
    """Run fn on the GUI thread from the test thread."""
    bridge.call.emit(fn)


def steps():
    # ---- 1  the key question: a request while a modal exec() is open
    on_gui(do_ask)                                   # a dialog opened by the PROGRAM, not by a command
    time.sleep(0.5)
    t0 = time.time()
    r = req("ui_tree", timeout=5)
    ok(r["ok"] and r["modal"] and r["modal"]["title"] == "Restore backup" and r["modal"]["class"] == "QMessageBox"
       and "12:00" in r["modal"]["text"] and time.time() - t0 < 2,
       "KEY QUESTION: a request is answered while a modal exec() is open, and ui_tree describes the dialog", r)
    ok({(b["text"], b["role"]) for b in r["modal"]["buttons"]} == {("Yes", "yes"), ("No", "no")},
       "the dialog's buttons come with their roles", r["modal"])
    ok(r["window"]["title"] == "Restore backup" and all(c["kind"] == "button" for c in r["controls"]),
       "with a modal open and no window named, ui_tree lists the dialog's own controls", r)
    r = req("ui_answer_modal", role="yes", expect="Restore the backup")
    ok(r["ok"] and r["pressed"] == "Yes" and r["closed"] is True and r["returned"] is True and r["modal"] is None,
       "ui_answer_modal by role closes it", r)
    time.sleep(0.2)
    ok(seen["ask"] == ["yes"], "... and the program received Yes", seen)
    r = req("ui_answer_modal", role="yes")
    ok(not r["ok"] and "no modal dialog is open" in r["error"], "ui_answer_modal with nothing open is an error", r)

    # ---- 2  ui_tree
    r = req("ui_tree", window="Test Window")
    by = {c["name"] or c.get("text"): c for c in r["controls"]}
    ok(r["ok"] and r["modal"] is None and any(w["title"] == "Test Window" and w["name"] == "testWin" for w in r["windows"]),
       "ui_tree lists the windows", r)
    ok(by["pingBtn"]["text"] == "Ping" and by["pingBtn"]["kind"] == "button" and by["pingBtn"]["enabled"] is True
       and by["Dead"]["enabled"] is False, "buttons: objectName, text without the shortcut mark, enabled", by)
    ok(by["Enable thing"]["kind"] == "checkbox" and by["Enable thing"]["checked"] is False
       and by["nameEdit"]["kind"] == "edit" and by["nameEdit"]["text"] == "Name:" and by["nameEdit"]["value"] == ""
       and by["modeCombo"]["items"] == ["Fast", "Careful", "Off"] and by["modeCombo"]["value"] == "Fast"
       and by["countSpin"]["value"] == 0 and by["countSpin"]["max"] == 10,
       "checkbox, edit (its label as its text), combo and spin box with their values", by)
    ok(any(c["kind"] == "tabs" and c["items"] == ["One", "Two"] and c["value"] == "One" for c in r["controls"]),
       "a tab bar with its tabs", r["controls"])
    ok([c.get("where") for c in r["controls"] if c.get("text") == "Same"] == ["Left", "Right"],
       "same-named buttons are told apart by where they are", r["controls"])
    r = req("ui_tree", window="Test Window", kinds=["combo"], limit=1)
    ok(r["ok"] and [c["kind"] for c in r["controls"]] == ["combo"] and r["truncated"] is False, "kinds and limit", r)
    r = req("ui_tree", window="Nope")
    ok(not r["ok"] and "no visible window" in r["error"] and "Test Window" in r["error"], "an unknown window is an error naming the windows", r)

    # ---- 3  ui_click
    r = req("ui_click", name="pingBtn")
    ok(r["ok"] and r["returned"] is True and r["clicked"]["text"] == "Ping" and seen["ping"] == 1 and os.path.isdir(r["backup"])
       and os.path.isfile(os.path.join(r["backup"], "modlist.txt")), "ui_click by objectName (the profile's lists backed up first)", r)
    r = req("ui_click", text="Ping", window="Test Window")
    ok(r["ok"] and seen["ping"] == 2, "ui_click by text", r)
    t0 = time.time()
    r = req("ui_click", name="applyBtn", timeout=5)
    ok(r["ok"] and r["returned"] is False and r["modal"]["title"] == "Apply" and "lose a master" in r["modal"]["text"]
       and len(r["modal"]["buttons"]) == 3 and time.time() - t0 < 3,
       "a click that opens a modal answers at once: returned false, the dialog described", r)
    r = req("ui_click", name="pingBtn", window="Test Window")
    ok(not r["ok"] and "a modal dialog is open" in r["error"] and seen["ping"] == 2, "nothing behind an open modal can be clicked", r)
    r = req("ui_tree", window="Test Window", kinds=["button"])
    ok(r["ok"] and r["modal"]["title"] == "Apply" and len(r["controls"]) >= 5, "... but it can still be read", r)
    r = req("ui_answer_modal", role="accept")
    ok(not r["ok"] and "2 buttons match" in r["error"] and "Apply and switch them off" in r["error"] and seen["apply"] == [],
       "two buttons share the accept role: role alone is refused, the texts are listed, nothing pressed", r)
    r = req("ui_answer_modal", text="Apply", expect="Something else")
    ok(not r["ok"] and "not the expected one" in r["error"] and seen["apply"] == [], "expect guards against the wrong dialog", r)
    r = req("ui_answer_modal", text="Apply, leave plugins as they are", expect="lose a master")
    ok(r["ok"] and r["closed"] is True and r["pressed"] == "Apply, leave plugins as they are", "answered by text", r)
    time.sleep(0.2)
    ok(seen["apply"] == ["keep"], "... and the program took that choice", seen)
    for text, want in (("Apply and switch them off", "all"), (None, "cancel")):
        r = req("ui_click", text="Apply", window="Test Window")
        ok(r["ok"] and r["returned"] is False, "Apply again opens the dialog again", r)
        r = req("ui_answer_modal", text=text) if text else req("ui_answer_modal", role="reject")
        time.sleep(0.2)
        ok(r["ok"] and seen["apply"][-1] == want, "the dialog's %s choice reaches the program" % want, (r, seen))

    # ---- 4  ui_set
    r = req("ui_set", text="Enable thing", value=True)
    ok(r["ok"] and r["value"] is True and r["applied"] is True and check.isChecked(), "checkbox on, read back", r)
    r = req("ui_set", text="Enable thing", value="yes")
    ok(not r["ok"] and "true or false" in r["error"], "a checkbox takes a real true/false", r)
    r = req("ui_set", text="Name:", value="Lydia")
    ok(r["ok"] and r["value"] == "Lydia" and edit.text() == "Lydia" and seen["edited"] == 1, "edit found by its label, set, read back (textEdited fired)", r)
    r = req("ui_set", name="modeCombo", value="Careful")
    ok(r["ok"] and r["value"] == "Careful" and combo.currentIndex() == 1 and seen["activated"] == [1], "combo by text (activated fired)", r)
    r = req("ui_set", name="modeCombo", value=2)
    ok(r["ok"] and r["value"] == "Off", "combo by index", r)
    r = req("ui_set", name="modeCombo", value="Nope")
    ok(not r["ok"] and "no item 'Nope'" in r["error"] and combo.currentText() == "Off", "an unknown combo item is refused, with the items", r)
    r = req("ui_set", name="countSpin", value=7)
    ok(r["ok"] and r["value"] == 7 and spin.value() == 7, "spin box", r)
    r = req("ui_set", name="countSpin", value=99)
    ok(not r["ok"] and "0..10" in r["error"] and spin.value() == 7, "a spin value out of range is refused", r)
    r = req("ui_set", kind="tabs", name="qt_tabwidget_tabbar", window="Test Window", value="Two")
    ok(r["ok"] and r["value"] == "Two" and tabs.currentIndex() == 1, "tab bar by tab text", r)
    r = req("ui_set", name="pingBtn", value=True)
    ok(not r["ok"] and "not a checkable" in r["error"], "ui_set on a plain button is refused", r)

    # ---- 5  safety
    r = req("ui_click", text="Same")
    ok(not r["ok"] and "2 widgets match" in r["error"] and "'Left'" in r["error"] and "'Right'" in r["error"] and "same" not in seen,
       "an ambiguous locator is refused with the candidates - nothing clicked", r)
    r = req("ui_click", text="Same", path="Test Window > Right")
    ok(r["ok"] and seen["same"] == ["Right"], "path picks one", r)
    r = req("ui_click", text="Same", index=0)
    ok(r["ok"] and seen["same"] == ["Right", "Left"], "index picks one", r)
    r = req("ui_click", text="Dead")
    ok(not r["ok"] and "disabled" in r["error"], "a disabled button is refused", r)
    r = req("ui_click", text="Nope")
    ok(not r["ok"] and "no visible control matches" in r["error"], "an unknown widget is an error", r)
    r = req("ui_click")
    ok(not r["ok"] and "say which widget" in r["error"], "a locator is required", r)
    busy["v"] = True
    r = req("ui_click", name="pingBtn")
    ok(not r["ok"] and r.get("refused") and "MO2 is in use" in r["error"] and seen["ping"] == 2, "a click while MO2 is in use is refused", r)
    r = req("ui_set", name="countSpin", value=1)
    ok(not r["ok"] and r.get("refused") and spin.value() == 7, "ui_set too", r)
    r = req("ui_tree", window="Test Window")
    ok(r["ok"], "ui_tree still reads", r)
    r = req("ui_click", name="pingBtn", confirm="the user, in chat")
    ok(r["ok"] and seen["ping"] == 3 and any("ui_click" in x and "confirm: the user, in chat" in x for x in logged),
       "with confirm it goes through and is logged", (r, logged[-2:]))
    busy["v"] = False
    # ---- 6  a dialog inside a dialog: a tool window run with exec(), and a question asked from inside it
    r = req("ui_click", name="toolBtn")
    ok(r["ok"] and r["returned"] is False and r["modal"]["title"] == "Tool"
       and [(x["text"], x["role"]) for x in r["modal"]["buttons"]] == [("Go", ""), ("Close", "")],
       "a tool window run with exec() is itself the modal: its push buttons are listed", r)
    r = req("ui_click", text="Go")
    ok(r["ok"] and r["returned"] is False and r["modal"]["title"] == "Sure?", "a click inside it opens a question on top", r)
    r = req("ui_click", text="Close")
    ok(not r["ok"] and "no visible" in r["error"] and "tool_closed" not in seen, "the tool window's own buttons are out of reach while the question is open", r)
    r = req("ui_answer_modal", role="yes", expect="Do it?")
    time.sleep(0.3)
    ok(r["ok"] and r["closed"] is True and r["modal"] and r["modal"]["title"] == "Tool" and seen["go"] == [True]
       and [x["text"] for x in r["modal"]["buttons"]] == ["Go", "Close"],
       "answering the question hands the tool window back as the modal", (r, seen))
    r = req("ui_click", text="Close")
    time.sleep(0.3)
    ok(r["ok"] and r["returned"] is True and seen.get("tool_closed") is True, "and the tool window closes by its own button", (r, seen))
    r = req("ui_tree")
    ok(r["ok"] and r["modal"] is None, "nothing modal is left open", r["modal"])
    # ---- 7  lists, tables and trees: read through the model, operated through the model
    r = req("ui_tree", window="Test Window", kinds=["view"])
    ok(r["ok"] and [(c["name"], c["class"], c["rows"], c["columns"], c["tree"]) for c in r["controls"]]
       == [("modTree", "QTreeView", 7, 2, True), ("", "QListWidget", 3, 1, False)], "ui_tree lists the views with their size", r["controls"])
    r = req("ui_items", name="modTree")
    ok(r["ok"] and r["total"] == 7 and [c["title"] for c in r["columns"]] == ["Mod", "Priority"]
       and r["rows"][0] == {"row": 0, "cells": ["Alpha", "0"], "checked": True}
       and r["rows"][1]["checked"] is False and r["rows"][4].get("children") is True and r["rows"][4]["expanded"] is False
       and r["rows"][6].get("enabled") is False and r["next"] is None, "ui_items: cells, ticked, rows with rows under them, a disabled row", r)
    r = req("ui_items", name="modTree", start=1, limit=2, columns=[0])
    ok(r["ok"] and [x["cells"] for x in r["rows"]] == [["Bravo"], ["Same"]] and r["next"] == 3, "paging and chosen columns", r)
    r = req("ui_items", name="modTree", find="lph")
    ok(r["ok"] and [x["row"] for x in r["rows"]] == [0], "find keeps the rows that hold the text", r)
    r = req("ui_items", name="modTree", parent=["Folder"])
    ok(r["ok"] and [x["cells"][0] for x in r["rows"]] == ["one.esp", "two.esp"] and r["total"] == 2, "the rows under a row, by its text", r)
    r = req("ui_items", kind="view", window="Test Window", index=1)
    ok(r["ok"] and [x["cells"] for x in r["rows"]] == [["red"], ["green"], ["blue"]], "a list with no name, by index", r)
    r = req("ui_items", window="Test Window")
    ok(not r["ok"] and "2 widgets match" in r["error"], "two lists and no name: refused, the candidates listed", r)
    r = req("ui_item", name="modTree", match="Bravo", action="check")
    ok(r["ok"] and r["applied"] is True and r["row"]["checked"] is True and r["was"]["checked"] is False
       and seen["ticked"] == [("Bravo", True)] and os.path.isdir(r["backup"]), "tick a row by its text: the model changed it (the program was told), backed up first", (r, seen.get("ticked")))
    r = req("ui_item", name="modTree", row=0, action="uncheck")
    ok(r["ok"] and r["applied"] is True and seen["ticked"][-1] == ("Alpha", False), "untick by row number", r)
    r = req("ui_item", name="modTree", row=0, action="uncheck")
    ok(r["ok"] and r["applied"] is True and len(seen["ticked"]) == 2, "unticking an unticked row changes nothing and says so", (r, seen["ticked"]))
    r = req("ui_item", name="modTree", match="Same", action="check")
    ok(not r["ok"] and "2 rows have 'Same'" in r["error"] and len(seen["ticked"]) == 2, "two rows with that text: refused, nothing ticked", r)
    r = req("ui_item", name="modTree", match="Folder", action="check")
    ok(not r["ok"] and "no box to tick" in r["error"], "a row with no box cannot be ticked", r)
    r = req("ui_items", name="modTree", find="Forced")
    ok(r["ok"] and r["rows"][0]["checked"] is True and r["rows"][0].get("checkable") is False
       and "checkable" not in req("ui_items", name="modTree", find="Alpha")["rows"][0],
       "a box that is shown but cannot be ticked says so (checkable false)", r)
    r = req("ui_item", name="modTree", match="Forced", action="uncheck")
    ok(not r["ok"] and "no box to tick" in r["error"], "... and ticking it is refused", r)
    r = req("ui_item", name="modTree", match="Locked", action="check")
    ok(not r["ok"] and "disabled" in r["error"], "a disabled row cannot be ticked", r)
    r = req("ui_item", name="modTree", match="Folder", action="expand")
    ok(r["ok"] and r["applied"] is True and r["row"]["expanded"] is True and tree_view.isExpanded(model.index(4, 0)), "open a row", r)
    r = req("ui_item", name="modTree", parent=[4], match="two.esp", action="select")
    ok(r["ok"] and r["applied"] is True and r["row"].get("selected") is True
       and tree_view.selectionModel().currentIndex().data() == "two.esp", "select a row under a row", r)
    r = req("ui_item", name="modTree", match="Folder", action="collapse")
    ok(r["ok"] and r["row"]["expanded"] is False, "close it again", r)
    r = req("ui_item", name="modTree", row=99, action="select")
    ok(not r["ok"] and "row must be 0..6" in r["error"], "a row that does not exist is an error", r)
    r = req("ui_item", name="modTree", row=1, action="paint")
    ok(not r["ok"] and "action is one of" in r["error"], "an unknown action is an error", r)
    busy["v"] = True
    r = req("ui_item", name="modTree", row=1, action="uncheck")
    ok(not r["ok"] and r.get("refused") and len(seen["ticked"]) == 2, "a tick while MO2 is in use is refused", r)
    r = req("ui_items", name="modTree", limit=1)
    ok(r["ok"], "reading the rows is not")
    busy["v"] = False

    # ---- 8  menus and tool bars
    r = req("ui_menus", window="Test Window")
    paths = {e["path"]: e for e in r["entries"]}
    ok(r["ok"] and {"File", "File > Open...", "File > Recent", "File > Recent > first.txt", "File > Gone", "View > Word wrap",
                    "Tools > Ask...", "Refresh"} <= set(paths), "ui_menus: every entry as a text path, shortcut marks and keys removed", sorted(paths))
    ok(paths["File > Gone"]["enabled"] is False and paths["View > Word wrap"]["checked"] is False
       and paths["File > Recent"].get("menu") is True and paths["Refresh"].get("name") == "actionRefresh",
       "entries say enabled, ticked, submenu and objectName", paths)
    r = req("ui_menus", window="Test Window", under="File > Recent")
    ok(r["ok"] and [e["path"] for e in r["entries"]] == ["File > Recent", "File > Recent > first.txt"], "under narrows the list", r)
    r = req("ui_menu", window="Test Window", path="File > Open...")
    ok(r["ok"] and r["returned"] is True and seen["menu"] == ["open"] and os.path.isdir(r["backup"]), "choose an entry by path", r)
    r = req("ui_menu", window="Test Window", path="File > Recent > first.txt")
    ok(r["ok"] and seen["menu"][-1] == "recent-first", "an entry inside a submenu", r)
    r = req("ui_menu", window="Test Window", name="actionRefresh")
    ok(r["ok"] and seen["menu"][-1] == "refresh", "a tool bar entry by its objectName", r)
    r = req("ui_menu", window="Test Window", path="View > Word wrap")
    ok(r["ok"] and r["checked"] is True and wrap.isChecked(), "a tickable entry reports its new state", r)
    r = req("ui_menu", window="Test Window", path="File > Gone")
    ok(not r["ok"] and "disabled" in r["error"], "a disabled entry is refused", r)
    r = req("ui_menu", window="Test Window", path="File > Recent")
    ok(not r["ok"] and "submenu" in r["error"], "an entry that only opens a submenu is refused", r)
    r = req("ui_menu", window="Test Window", path="File > Nope")
    ok(not r["ok"] and "no menu entry" in r["error"], "an unknown entry is an error", r)
    r = req("ui_menu", window="Test Window", path="Tools > Ask...")
    ok(r["ok"] and r["returned"] is False and r["modal"]["title"] == "Restore backup", "an entry that opens a dialog answers with the dialog described", r)
    r = req("ui_menu", window="Test Window", path="File > Open...")
    ok(not r["ok"] and "a modal dialog is open" in r["error"] and seen["menu"].count("open") == 1, "no menu behind an open dialog", r)
    r = req("ui_menu", path="File > Open...")
    ok(not r["ok"] and "a modal dialog is open" in r["error"] and seen["menu"].count("open") == 1,
       "... also when no window is named: the refusal names the dialog, not a missing entry", r)
    r = req("ui_menus")
    ok(r["ok"] and r["total"] == 0, "with a dialog open and no window named, the dialog's own (no) menus are listed", r)
    r = req("ui_item", name="modTree", window="Test Window", row=1, action="uncheck")
    ok(not r["ok"] and "a modal dialog is open" in r["error"], "no list behind an open dialog", r)
    r = req("ui_answer_modal", role="no")
    ok(r["ok"] and r["closed"] is True, "the dialog answered", r)
    r = req("ui_tree", window="Test Window", limit=0)
    ok(not r["ok"] and "limit" in r["error"], "a bad limit is an error, not a crash", r)


result = {"exc": None, "done": False}


def worker():
    try:
        steps()
    except BaseException as exc:  # noqa: BLE001
        result["exc"] = exc
    result["done"] = True


threading.Thread(target=worker, daemon=True).start()
poll = QTimer()
poll.timeout.connect(lambda: app.quit() if result["done"] else None)
poll.start(50)
QTimer.singleShot(120000, app.quit)      # never hang a test run
app.exec()
shutil.rmtree(T, ignore_errors=True)
if not result["done"] or result["exc"] is not None or failed:
    print("FAILED", result["exc"] or "timed out", flush=True)
    sys.exit(1)
print("ALL PASS", n)
