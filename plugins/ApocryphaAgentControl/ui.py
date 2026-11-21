r"""MO2 Agent Control - the window commands (Qt only, no mobase, so the tests run this very code without MO2).

  ui_tree          what is on screen: the visible windows, the open modal dialog (its text and buttons), and the controls of
                   one window - buttons, checkboxes, radio buttons, edits, combo boxes, spin boxes, tab bars
  ui_click         presses one button, found by objectName, by its text, or by a path of names
  ui_answer_modal  presses a button of the open modal dialog, by role (accept, reject, yes, no ...) or by text
  ui_set           sets a checkbox / radio button, an edit, a combo box, a spin box or a tab bar, and reads the value back
  ui_items         the rows of a list, table or tree (kind "view"): cells, ticked, selected, has rows under it
  ui_item          selects, ticks / unticks, opens / closes or scrolls to one row - through the list's own model
  ui_menus         the entries of a window's menu bar and tool bars, as text paths
  ui_menu          chooses one of them (what a click on the entry does)

No mouse or keyboard input is sent and no window is moved or raised: each command calls the widget's own method
(click(), setText() ...), which works whether or not the window is in front, visible on screen, or minimised.

FINDING A WIDGET. A locator is `name` (the widget's objectName) and/or `text` (what it shows, without the "&" of a
keyboard shortcut; for an edit, combo or spin box, the text of its label), optionally narrowed by `kind`, by `window`
(a window's title or objectName) and by `path` ("Outer > Inner": each part is a window title, an objectName, a group
box's title or a tab's text, each inside the one before). A locator that matches more than one widget is REFUSED with
the candidates listed - nothing is ever picked by guess; add `window`, `path` or `index` (0-based, in the order ui_tree
lists them). While a modal dialog is open, only that dialog's widgets can be acted on.

WHEN THE REPLY COMES. Pressing a button may open a modal dialog, and then the press does not return until the dialog
is closed. So an action runs just after the command handler has returned, and the reply is sent as soon as the action
returns - or, if it has not returned after `wait_ms` (default 400), with "returned": false and the dialog it is waiting
in ("modal"). Answer that dialog with ui_answer_modal. Replies are English whatever MO2's language is (tools read them).
"""
try:
    from PyQt6.QtCore import QItemSelectionModel, QModelIndex, Qt, QTimer
    from PyQt6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractSpinBox, QApplication, QHeaderView, QMenuBar, QToolBar,
                                 QTreeView, QCheckBox, QComboBox, QDialog,
                                 QDialogButtonBox, QDoubleSpinBox, QGroupBox, QLabel, QLineEdit, QMessageBox,
                                 QPlainTextEdit, QRadioButton, QSpinBox, QTabBar, QTabWidget, QTextEdit, QWidget)
except ImportError:  # MO2 before 2.5
    from PyQt5.QtCore import QItemSelectionModel, QModelIndex, Qt, QTimer
    from PyQt5.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractSpinBox, QApplication, QHeaderView, QMenuBar, QToolBar,
                                 QTreeView, QCheckBox, QComboBox, QDialog,
                                 QDialogButtonBox, QDoubleSpinBox, QGroupBox, QLabel, QLineEdit, QMessageBox,
                                 QPlainTextEdit, QRadioButton, QSpinBox, QTabBar, QTabWidget, QTextEdit, QWidget)

ROLES = {-1: "invalid", 0: "accept", 1: "reject", 2: "destructive", 3: "action", 4: "help", 5: "yes", 6: "no",
         7: "reset", 8: "apply"}
KINDS = ("button", "checkbox", "radio", "edit", "text", "combo", "spin", "tabs", "label", "view")
MAX_ITEMS = 100
MAX_TEXT = 2000
DEFAULT_LIMIT = 300
DEFAULT_WAIT_MS = 400


def clean(text):
    """A widget's text as a person reads it: no "&" shortcut marks ("&&" is a real "&"), no outer spaces."""
    return str(text or "").replace("&&", "\0").replace("&", "").replace("\0", "&").strip()


def _num(enum_value):
    return int(getattr(enum_value, "value", enum_value))


def _cut(text):
    text = str(text or "")
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "..."


# ---- what a widget is -----------------------------------------------------------------------------------------------------
def kind_of(w):
    if isinstance(w, QCheckBox):
        return "checkbox"
    if isinstance(w, QRadioButton):
        return "radio"
    if isinstance(w, QAbstractButton):
        return "button"
    if isinstance(w, QLineEdit):
        # the edit inside a combo box or a spin box is part of that control, not one of its own
        return None if isinstance(w.parent(), (QComboBox, QAbstractSpinBox)) else "edit"
    if isinstance(w, (QPlainTextEdit, QTextEdit)):
        return "text"
    if isinstance(w, QComboBox):
        return "combo"
    if isinstance(w, (QSpinBox, QDoubleSpinBox)):
        return "spin"
    if isinstance(w, QTabBar):
        return "tabs"
    if isinstance(w, QLabel):
        return "label"
    if isinstance(w, QHeaderView):
        return None                     # a table's header belongs to its table
    if isinstance(w, QAbstractItemView):
        # the drop-down list of a combo box and the list of a date or completer pop-up belong to that control
        p = w.parent()
        while p is not None:
            if isinstance(p, QComboBox):
                return None
            p = p.parent()
        return "view"
    return None


def _buddies(root):
    """{widget: its label's text} for every label in root that names a buddy."""
    out = {}
    for lab in root.findChildren(QLabel):
        b = lab.buddy()
        if b is not None:
            out[b] = clean(lab.text())
    return out


def _where(w, root):
    """The named or titled ancestors of w below root, outermost first - enough to tell two same-named widgets apart."""
    parts = []
    p = w.parent()
    while p is not None and p is not root:
        if isinstance(p, QGroupBox) and clean(p.title()):
            parts.append(clean(p.title()))
        elif p.objectName() and not p.objectName().startswith("qt_"):
            parts.append(p.objectName())
        gp = p.parent()
        if isinstance(gp, QTabWidget) or (gp is not None and isinstance(gp.parent(), QTabWidget)):
            tw = gp if isinstance(gp, QTabWidget) else gp.parent()
            i = tw.indexOf(p)
            if i >= 0:
                parts.append(clean(tw.tabText(i)))
        p = p.parent()
    return " > ".join(reversed(parts))


def describe(w, root=None, buddies=None):
    k = kind_of(w)
    if k == "view":
        return describe_view(w, root)
    d = {"kind": k, "class": type(w).__name__, "name": w.objectName(), "enabled": bool(w.isEnabled()),
         "visible": bool(w.isVisible())}
    if root is not None:
        d["where"] = _where(w, root)
    if k in ("button", "checkbox", "radio"):
        d["text"] = clean(w.text())
        if not d["text"] and w.toolTip():
            d["tooltip"] = clean(w.toolTip())
        if w.isCheckable():
            d["checked"] = bool(w.isChecked())
    elif k == "edit":
        d["value"] = _cut(w.text())
        d["read_only"] = bool(w.isReadOnly())
        if w.placeholderText():
            d["placeholder"] = w.placeholderText()
    elif k == "text":
        d["value"] = _cut(w.toPlainText())
        d["read_only"] = bool(w.isReadOnly())
    elif k == "combo":
        d["value"] = w.currentText()
        d["index"] = int(w.currentIndex())
        d["items"] = [w.itemText(i) for i in range(min(w.count(), MAX_ITEMS))]
        d["count"] = int(w.count())
        d["editable"] = bool(w.isEditable())
    elif k == "spin":
        d["value"] = w.value()
        d["min"], d["max"] = w.minimum(), w.maximum()
    elif k == "tabs":
        d["items"] = [clean(w.tabText(i)) for i in range(w.count())]
        d["index"] = int(w.currentIndex())
        d["value"] = clean(w.tabText(w.currentIndex())) if w.count() else ""
    elif k == "label":
        d["text"] = _cut(clean(w.text()))
    if k in ("edit", "text", "combo", "spin") and buddies and w in buddies:
        d["text"] = buddies[w]
    return d


# ---- windows and the modal dialog -----------------------------------------------------------------------------------------
def windows():
    return [w for w in QApplication.topLevelWidgets() if w.isWindow() and w.isVisible()
            and type(w).__name__ not in ("QMenu", "QTipLabel", "QToolTip")]


def describe_window(w):
    return {"title": clean(w.windowTitle()), "name": w.objectName(), "class": type(w).__name__,
            "modal": bool(w.isModal()), "active": w is QApplication.activeWindow()}


def modal():
    return QApplication.activeModalWidget()


def modal_buttons(dlg):
    """[(button, role name)] of a dialog: a message box's own buttons, else its button boxes', else its push buttons."""
    if isinstance(dlg, QMessageBox):
        return [(b, ROLES.get(_num(dlg.buttonRole(b)), "invalid")) for b in dlg.buttons()]
    # only what sits in THIS dialog: a child dialog (a question it asked, closed but not yet deleted) is still among
    # its children, and that one's buttons are not this dialog's
    out = []
    for box in dlg.findChildren(QDialogButtonBox):
        if box.window() is dlg and box.isVisible():
            out += [(b, ROLES.get(_num(box.buttonRole(b)), "invalid")) for b in box.buttons()]
    if not out:
        out = [(b, "") for b in dlg.findChildren(QAbstractButton)
               if kind_of(b) == "button" and b.isVisible() and b.window() is dlg]
    return out


def describe_modal(dlg=None):
    dlg = dlg if dlg is not None else modal()
    if dlg is None:
        return None
    d = describe_window(dlg)
    if isinstance(dlg, QMessageBox):
        d["text"] = _cut(clean(dlg.text()))
        if dlg.informativeText():
            d["informative"] = _cut(clean(dlg.informativeText()))
        if dlg.detailedText():
            d["detailed"] = _cut(dlg.detailedText())
        default, escape = dlg.defaultButton(), dlg.escapeButton()
    else:
        default = escape = None
    d["buttons"] = []
    for b, role in modal_buttons(dlg):
        e = {"text": clean(b.text()), "role": role, "enabled": bool(b.isEnabled())}
        if b is default or (hasattr(b, "isDefault") and b.isDefault()):
            e["default"] = True
        if b is escape:
            e["escape"] = True
        d["buttons"].append(e)
    return d


# ---- finding ---------------------------------------------------------------------------------------------------------------
def _find_window(spec):
    hits = [w for w in windows() if spec in (clean(w.windowTitle()), w.objectName())]
    if not hits:
        raise ValueError("no visible window titled or named %r - windows: %s"
                         % (spec, ", ".join(repr(clean(w.windowTitle()) or w.objectName()) for w in windows()) or "none"))
    if len(hits) > 1:
        raise ValueError("%d visible windows are titled or named %r" % (len(hits), spec))
    return hits[0]


def _narrow(roots, part):
    """The one widget inside `roots` that the path part names: a window, an objectName, a group box title, a tab's page."""
    hits = []
    for root in roots:
        if part in (clean(root.windowTitle()) if root.isWindow() else "", root.objectName()):
            hits.append(root)
        for w in root.findChildren(QWidget):
            if w.objectName() == part or (isinstance(w, QGroupBox) and clean(w.title()) == part):
                hits.append(w)
            elif isinstance(w, QTabWidget):
                hits += [w.widget(i) for i in range(w.count()) if clean(w.tabText(i)) == part]
    uniq = []
    for h in hits:
        if h is not None and not any(h is u for u in uniq):
            uniq.append(h)
    if not uniq:
        raise ValueError("nothing in the path is named %r" % part)
    if len(uniq) > 1:
        raise ValueError("%d things are named %r - make the path more exact" % (len(uniq), part))
    return uniq[0]


def scope(a, acting):
    """The widgets a locator searches: one window, narrowed by path. While a modal dialog is open an ACTION may only
    reach into that dialog; a read may still name another window."""
    dlg = modal()
    if a.get("window"):
        roots = [_find_window(str(a["window"]))]
        if acting and dlg is not None and roots[0] is not dlg:
            raise ValueError("a modal dialog is open (%r) - answer it first (ui_answer_modal); nothing behind it can be "
                             "acted on" % (clean(dlg.windowTitle()) or type(dlg).__name__))
    elif dlg is not None:
        roots = [dlg]
    else:
        roots = windows()
    path = a.get("path")
    if path:
        if not isinstance(path, str):
            raise ValueError("path is text: 'Outer > Inner'")
        for part in [p.strip() for p in path.split(">") if p.strip()]:
            roots = [_narrow(roots, part)]
    return roots


def controls(roots, kinds=None, include_hidden=False, labels=False):
    """[(widget, root)] of the controls under the roots, in Qt's child order (the order ui_tree lists and `index` counts)."""
    out = []
    for root in roots:
        cands = ([root] if kind_of(root) else []) + root.findChildren(QWidget)
        for w in cands:
            k = kind_of(w)
            if k is None or (k == "label" and not labels) or (kinds and k not in kinds):
                continue
            if not include_hidden and not w.isVisible():
                continue
            if w.window() is not root.window():
                continue                    # a child dialog's widgets belong to that dialog
            out.append((w, root.window()))
    return out


def locate(a, acting=True, want=None):
    """The one widget the locator names. `want`: the kinds the command can act on."""
    name, text, kind = a.get("name"), a.get("text"), a.get("kind")
    if not name and not text and kind != "view":      # a list often has neither: kind=view, then window / path / index
        raise ValueError("say which widget: name (its objectName) and/or text (what it shows) - ui_tree lists both")
    if kind and kind not in KINDS:
        raise ValueError("kind is one of %s" % ", ".join(KINDS))
    kinds = {kind} if kind else (set(want) if want else None)
    roots = scope(a, acting)
    hits = []
    for w, root in controls(roots, kinds, include_hidden=False, labels=False):
        d = describe(w, root, _buddies(root))
        if name and d["name"] != name:
            continue
        if text and d.get("text", d.get("tooltip", "")) != text and d.get("tooltip", "") != text:
            continue
        hits.append((w, d))
    if not hits:
        raise ValueError("no visible %s matches %s - ui_tree lists what is there"
                         % (kind or "control", ", ".join("%s=%r" % (k, v) for k, v in (("name", name), ("text", text)) if v)))
    if a.get("index") is not None:
        i = a["index"]
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(hits):
            raise ValueError("index must be 0..%d (%d widgets match)" % (len(hits) - 1, len(hits)))
        return hits[i]
    if len(hits) > 1:
        some = "; ".join("[%d] %s %r in %r" % (i, d["kind"], d.get("text") or d["name"], d.get("where") or "the window")
                         for i, (_w, d) in enumerate(hits[:10]))
        raise ValueError("%d widgets match - nothing was done. Add window, path or index: %s" % (len(hits), some))
    return hits[0]


# ---- the commands ---------------------------------------------------------------------------------------------------------
def tree(a):
    limit = a.get("limit", DEFAULT_LIMIT)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit is a whole number above 0")
    kinds = a.get("kinds")
    if kinds is not None and (not isinstance(kinds, list) or any(k not in KINDS for k in kinds)):
        raise ValueError("kinds is a list from %s" % ", ".join(KINDS))
    roots = scope(a, acting=False)
    out = {"windows": [describe_window(w) for w in windows()], "modal": describe_modal(), "controls": [], "truncated": False}
    if len(roots) == 1:
        out["window"] = describe_window(roots[0].window())
    buddy_maps = {}
    for w, root in controls(roots, set(kinds) if kinds else None, bool(a.get("hidden")), bool(a.get("labels"))):
        if len(out["controls"]) >= limit:
            out["truncated"] = True
            break
        if id(root) not in buddy_maps:
            buddy_maps[id(root)] = _buddies(root)
        d = describe(w, root, buddy_maps[id(root)])
        if len(roots) > 1:
            d["window"] = clean(root.windowTitle()) or root.objectName()
        out["controls"].append(d)
    return out


def _wait_ms(a):
    ms = a.get("wait_ms", DEFAULT_WAIT_MS)
    if not isinstance(ms, int) or isinstance(ms, bool) or not 0 <= ms <= 60000:
        raise ValueError("wait_ms is 0..60000")
    return ms


def _later(target, action, after, wait_ms):
    """A function for core.Dispatcher: runs `action` once the handler has returned, and answers when it returns - or
    after wait_ms if it is still inside a dialog by then."""
    def start(finish):
        state = {"done": False}

        def run():
            try:
                action()
                result = dict(target, returned=True, modal=describe_modal(), **after())
            except Exception as exc:  # noqa: BLE001
                state["done"] = True
                finish(exc)
                return
            state["done"] = True
            finish(result)

        def watch():
            if not state["done"]:
                finish(dict(target, returned=False, modal=describe_modal(),
                            note="the action has not returned yet: it is waiting inside a dialog - ui_tree shows it, "
                                 "ui_answer_modal answers it"))

        QTimer.singleShot(0, run)
        QTimer.singleShot(wait_ms, watch)
    return start


def _usable(w, d):
    if not d["enabled"]:
        raise ValueError("%s %r is disabled" % (d["kind"], d.get("text") or d["name"]))


def click(a):
    w, d = locate(a, want=("button", "checkbox", "radio"))
    _usable(w, d)
    return _later({"clicked": d}, w.click, lambda: {}, _wait_ms(a))


def answer_modal(a):
    dlg = modal()
    if dlg is None:
        raise ValueError("no modal dialog is open")
    info = describe_modal(dlg)
    expect = a.get("expect")
    if expect:
        hay = " ".join(str(info.get(k, "")) for k in ("title", "text", "informative"))
        if str(expect) not in hay:
            raise ValueError("the open dialog is not the expected one (%r is not in its title or text: %r / %r) - nothing "
                             "was pressed" % (expect, info.get("title"), info.get("text", "")))
    role, text = a.get("role"), a.get("text")
    if bool(role) == bool(text):
        raise ValueError("give role (accept, reject, yes, no, apply, destructive, action, help, reset) or text (the "
                         "button's text) - one of them")
    buttons = modal_buttons(dlg)
    if role:
        role = str(role).lower().replace("role", "")
        if role not in ROLES.values() or role == "invalid":
            raise ValueError("role is one of accept, reject, yes, no, apply, destructive, action, help, reset")
        hits = [b for b, r in buttons if r == role]
    else:
        hits = [b for b, _r in buttons if clean(b.text()) == text]
    listed = ", ".join("%r (%s)" % (clean(b.text()), r or "no role") for b, r in buttons) or "none"
    if len(hits) > 1:
        raise ValueError("%d buttons match - nothing was pressed. Use text: %s" % (len(hits), listed))
    if not hits:
        if role in ("accept", "reject") and isinstance(dlg, QDialog) and not isinstance(dlg, QMessageBox) and not buttons:
            return _later({"answered": info, "by": role}, dlg.accept if role == "accept" else dlg.reject,
                          lambda: {"closed": not dlg.isVisible()}, _wait_ms(a))
        raise ValueError("the dialog has no such button - its buttons: %s" % listed)
    b = hits[0]
    if not b.isEnabled():
        raise ValueError("that button is disabled")
    return _later({"answered": info, "pressed": clean(b.text())}, b.click, lambda: {"closed": not dlg.isVisible()},
                  _wait_ms(a))


def _combo_index(w, value):
    if isinstance(value, bool):
        raise ValueError("a combo box takes an item's text or its index")
    if isinstance(value, int):
        if not 0 <= value < w.count():
            raise ValueError("the combo box has items 0..%d" % (w.count() - 1))
        return value
    hits = [i for i in range(w.count()) if w.itemText(i) == str(value)]
    if not hits:
        return -1
    return hits[0]


def set_value(a):
    if "value" not in a:
        raise ValueError("ui_set needs value")
    value = a["value"]
    w, d = locate(a, want=("checkbox", "radio", "button", "edit", "text", "combo", "spin", "tabs"))
    _usable(w, d)
    k = d["kind"]
    if k in ("checkbox", "radio", "button"):
        if not w.isCheckable():
            raise ValueError("that button is not a checkable one - ui_click presses it")
        if not isinstance(value, bool):
            raise ValueError("a %s takes true or false" % k)

        def action():
            if w.isChecked() != value:
                w.click()               # as a person does it: clicked and toggled both fire
        read = lambda: bool(w.isChecked())  # noqa: E731
    elif k == "edit":
        if w.isReadOnly():
            raise ValueError("that edit is read-only")
        value = str(value)

        def action():
            w.setText(value)
            w.textEdited.emit(value)    # setText alone tells the program less than typing does
            w.editingFinished.emit()
        read = lambda: w.text()  # noqa: E731
    elif k == "text":
        if w.isReadOnly():
            raise ValueError("that text box is read-only")
        value = str(value)
        action = lambda: w.setPlainText(value)  # noqa: E731
        read = lambda: w.toPlainText()  # noqa: E731
    elif k == "combo":
        i = _combo_index(w, value)
        if i < 0 and not w.isEditable():
            raise ValueError("the combo box has no item %r - its items: %s"
                             % (value, ", ".join(repr(w.itemText(j)) for j in range(min(w.count(), 30)))))

        def action():
            if i >= 0:
                w.setCurrentIndex(i)
                w.activated.emit(i)     # what a pick by hand emits besides currentIndexChanged
            else:
                w.setEditText(str(value))
        value = w.itemText(i) if i >= 0 else str(value)
        read = lambda: w.currentText()  # noqa: E731
    elif k == "spin":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("a spin box takes a number")
        if not w.minimum() <= value <= w.maximum():
            raise ValueError("the spin box takes %s..%s" % (w.minimum(), w.maximum()))

        def action():
            w.setValue(value)
            w.editingFinished.emit()
        read = lambda: w.value()  # noqa: E731
    else:   # tabs
        items = [clean(w.tabText(j)) for j in range(w.count())]
        if isinstance(value, int) and not isinstance(value, bool):
            i = value
        else:
            i = items.index(str(value)) if str(value) in items else -1
        if not 0 <= i < w.count():
            raise ValueError("no such tab - tabs: %s" % ", ".join(repr(t) for t in items))
        if not w.isTabEnabled(i):
            raise ValueError("that tab is disabled")
        value = items[i]
        action = lambda: w.setCurrentIndex(i)  # noqa: E731
        read = lambda: clean(w.tabText(w.currentIndex()))  # noqa: E731

    def after():
        now = read()
        return {"value": now, "applied": now == value}
    return _later({"set": d, "asked": value}, action, after, _wait_ms(a))


# ---- lists, tables and trees (QAbstractItemView), read and operated through their MODEL -----------------------------------
# A view shows a model; everything here asks the model the view is showing (its proxy included), so a row is what the
# person sees in that row - sorted and filtered as on screen. Nothing is painted or clicked: a row is selected through
# the view's selection model, ticked through the model's own check-state role (the call a click on the box makes),
# opened with expand(), brought into sight with scrollTo().
DEFAULT_ROWS = 100
MAX_ROWS = 1000
MAX_COLUMNS = 40
ITEM_ACTIONS = ("select", "check", "uncheck", "expand", "collapse", "scroll_to")


def _check_role():
    return Qt.ItemDataRole.CheckStateRole if hasattr(Qt, "ItemDataRole") else Qt.CheckStateRole


def _display_role():
    return Qt.ItemDataRole.DisplayRole if hasattr(Qt, "ItemDataRole") else Qt.DisplayRole


def _ncols(m, idx):
    try:
        return int(m.columnCount(idx))
    except TypeError:       # a plain list model keeps columnCount to itself: it always has one column
        return 1


def _has_rows(m, idx):
    try:
        return bool(m.hasChildren(idx))
    except TypeError:       # a plain list model: a row never has rows under it
        return False


def _checked(index):
    """True / False / "partial" for a checkable cell, None when the cell has no box."""
    v = index.data(_check_role())
    if v is None:
        return None
    n = _num(v)
    return True if n == 2 else False if n == 0 else "partial"


def _flag(index, name):
    flags = index.flags()
    scoped = getattr(Qt, "ItemFlag", Qt)
    return bool(flags & getattr(scoped, name))


def _cell(index):
    v = index.data(_display_role())
    return "" if v is None else _cut(str(v))


def view_columns(view):
    m = view.model()
    if m is None:
        return []
    horizontal = Qt.Orientation.Horizontal if hasattr(Qt, "Orientation") else Qt.Horizontal
    out = []
    for c in range(min(_ncols(m, QModelIndex()), MAX_COLUMNS)):
        h = m.headerData(c, horizontal, _display_role())
        out.append({"column": c, "title": "" if h is None else clean(str(h)), "hidden": _column_hidden(view, c)})
    return out


def _column_hidden(view, c):
    try:
        return bool(view.isColumnHidden(c))
    except (AttributeError, TypeError):
        return False


def describe_view(w, root=None):
    m = w.model()
    d = {"kind": "view", "class": type(w).__name__, "name": w.objectName(), "enabled": bool(w.isEnabled()),
         "visible": bool(w.isVisible()), "rows": int(m.rowCount(QModelIndex())) if m is not None else 0,
         "columns": int(_ncols(m, QModelIndex())) if m is not None else 0,
         "tree": isinstance(w, QTreeView)}
    if root is not None:
        d["where"] = _where(w, root)
    return d


def _parent_index(view, parent):
    """The index a `parent` path names: a list of row numbers and / or first-column texts, outermost first."""
    m = view.model()
    idx = QModelIndex()
    for step in parent or []:
        n = m.rowCount(idx)
        if isinstance(step, int) and not isinstance(step, bool):
            if not 0 <= step < n:
                raise ValueError("parent row %d does not exist (rows 0..%d)" % (step, n - 1))
            idx = m.index(step, 0, idx)
        else:
            hits = [r for r in range(n) if _cell(m.index(r, 0, idx)) == str(step)]
            if len(hits) != 1:
                raise ValueError("%d rows are named %r at that level - give the row number" % (len(hits), step))
            idx = m.index(hits[0], 0, idx)
        if m.canFetchMore(idx):
            m.fetchMore(idx)            # a lazy tree (MO2's Data tab) loads a folder's rows when it is first opened
    return idx


def _row(view, parent_idx, r, columns):
    m = view.model()
    first = m.index(r, 0, parent_idx)
    row = {"row": r, "cells": [_cell(m.index(r, c, parent_idx)) for c in columns]}
    chk = _checked(first)
    if chk is not None:
        row["checked"] = chk
        if not _flag(first, "ItemIsUserCheckable"):
            row["checkable"] = False       # the box is shown but is not the person's to tick (a game's own master)
    sel = view.selectionModel()
    if sel is not None and sel.isRowSelected(r, parent_idx):
        row["selected"] = True
    if _has_rows(m, first):
        row["children"] = True
        if isinstance(view, QTreeView):
            row["expanded"] = bool(view.isExpanded(first))
    if not _flag(first, "ItemIsEnabled"):
        row["enabled"] = False
    return row


def _locate_view(a, acting):
    w, d = locate(dict(a, kind="view"), acting=acting, want=("view",))
    if w.model() is None:
        raise ValueError("that list has no content model")
    return w, d


def items(a):
    """ui_items: the rows of one list, table or tree."""
    w, d = _locate_view(a, acting=False)
    m = w.model()
    start, limit = a.get("start", 0), a.get("limit", DEFAULT_ROWS)
    for v, what in ((start, "start"), (limit, "limit")):
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError("%s is a whole number, 0 or more" % what)
    limit = min(limit, MAX_ROWS)
    cols = view_columns(w)
    want = a.get("columns")
    if want is not None:
        if not isinstance(want, list) or not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < len(cols) for c in want):
            raise ValueError("columns is a list of column numbers 0..%d" % (len(cols) - 1))
        use = want
    else:
        use = [c["column"] for c in cols if not c["hidden"]]
    parent_idx = _parent_index(w, a.get("parent"))
    total = m.rowCount(parent_idx)
    find = a.get("find")
    rows = []
    r = start
    while r < total and len(rows) < limit:
        if find is None or str(find).lower() in " ".join(_cell(m.index(r, c, parent_idx)) for c in use).lower():
            rows.append(_row(w, parent_idx, r, use))
        r += 1
    out = {"view": describe_view(w, w.window()), "columns": [cols[c] for c in use], "total": int(total), "start": start,
           "rows": rows, "next": r if r < total else None}
    if a.get("parent"):
        out["parent"] = a["parent"]
    return out


def _target_row(view, a):
    m = view.model()
    parent_idx = _parent_index(view, a.get("parent"))
    n = m.rowCount(parent_idx)
    row, match = a.get("row"), a.get("match")
    if (row is None) == (match is None):
        raise ValueError("say which row: row (its number, as ui_items shows it) or match (the exact text of a cell) - one of them")
    if row is not None:
        if not isinstance(row, int) or isinstance(row, bool) or not 0 <= row < n:
            raise ValueError("row must be 0..%d" % (n - 1))
        return parent_idx, row
    col = a.get("column", 0)
    if not isinstance(col, int) or isinstance(col, bool) or not 0 <= col < _ncols(m, parent_idx):
        raise ValueError("column must be 0..%d" % (_ncols(m, parent_idx) - 1))
    hits = [r for r in range(n) if _cell(m.index(r, col, parent_idx)) == str(match)]
    if not hits:
        raise ValueError("no row has %r in column %d - ui_items lists the rows" % (match, col))
    if len(hits) > 1:
        raise ValueError("%d rows have %r in column %d - nothing was done; give the row number (rows %s)"
                         % (len(hits), match, col, ", ".join(str(h) for h in hits[:10])))
    return parent_idx, hits[0]


def item(a):
    """ui_item: select / check / uncheck / expand / collapse / scroll_to one row."""
    action = a.get("action")
    if action not in ITEM_ACTIONS:
        raise ValueError("action is one of %s" % ", ".join(ITEM_ACTIONS))
    w, d = _locate_view(a, acting=True)
    _usable(w, d)
    m = w.model()
    parent_idx, r = _target_row(w, a)
    first = m.index(r, 0, parent_idx)
    before = _row(w, parent_idx, r, [0])
    if action in ("check", "uncheck"):
        if _checked(first) is None or not _flag(first, "ItemIsUserCheckable"):
            raise ValueError("that row has no box to tick")
        if not _flag(first, "ItemIsEnabled"):
            raise ValueError("that row is disabled")
        want = action == "check"
        state = getattr(getattr(Qt, "CheckState", Qt), "Checked" if want else "Unchecked")

        def act():
            if _checked(m.index(r, 0, parent_idx)) is not want:
                if not m.setData(m.index(r, 0, parent_idx), state, _check_role()):
                    raise ValueError("the list refused the change")
        after = lambda: {"row": _row(w, parent_idx, r, [0]), "applied": _checked(m.index(r, 0, parent_idx)) is want}  # noqa: E731
    elif action == "select":
        flag = QItemSelectionModel.SelectionFlag if hasattr(QItemSelectionModel, "SelectionFlag") else QItemSelectionModel
        how = flag.ClearAndSelect | flag.Rows

        def act():
            w.selectionModel().setCurrentIndex(m.index(r, 0, parent_idx), how)
            w.scrollTo(m.index(r, 0, parent_idx))
        after = lambda: {"row": _row(w, parent_idx, r, [0]), "applied": bool(w.selectionModel().isRowSelected(r, parent_idx))}  # noqa: E731
    elif action in ("expand", "collapse"):
        if not isinstance(w, QTreeView):
            raise ValueError("only a tree has rows to open")
        if not _has_rows(m, first):
            raise ValueError("that row has nothing under it")
        want = action == "expand"

        def act():
            w.setExpanded(m.index(r, 0, parent_idx), want)
        after = lambda: {"row": _row(w, parent_idx, r, [0]), "applied": bool(w.isExpanded(m.index(r, 0, parent_idx))) is want}  # noqa: E731
    else:   # scroll_to
        def act():
            w.scrollTo(m.index(r, 0, parent_idx))
        after = lambda: {"row": _row(w, parent_idx, r, [0]), "applied": True}  # noqa: E731
    return _later({"view": d, "action": action, "was": before}, act, after, _wait_ms(a))


# ---- menus: every QAction of a window's menu bar, its tool bars and the menus they open ------------------------------------
def _action_text(act):
    return clean(str(act.text() or "").split("\t")[0])


def _menu_of(act):
    try:
        return act.menu()
    except (AttributeError, RuntimeError):
        return None


def _walk_actions(actions, prefix, out, depth=0):
    for act in actions:
        if act.isSeparator() or not act.isVisible():
            continue
        text = _action_text(act) or clean(act.toolTip()) or act.objectName()
        if not text:
            continue
        path = prefix + [text]
        sub = _menu_of(act)
        row = {"path": " > ".join(path), "enabled": bool(act.isEnabled())}
        if act.objectName():
            row["name"] = act.objectName()
        if act.isCheckable():
            row["checked"] = bool(act.isChecked())
        if sub is not None:
            row["menu"] = True
        out.append((row, act))
        if sub is not None and depth < 6:
            _walk_actions(sub.actions(), path, out, depth + 1)


def _menu_roots(a, acting):
    # only `window` narrows a menu search: `path` and `name` here mean the ENTRY, not a place in the window
    roots = scope({"window": a.get("window")} if a.get("window") else {}, acting)
    wins = []
    for r in roots:
        w = r.window()
        if not any(w is x for x in wins):
            wins.append(w)
    return wins


def _all_actions(a, acting):
    out = []
    for win in _menu_roots(a, acting):
        for bar in win.findChildren(QMenuBar):
            if bar.window() is win:
                _walk_actions(bar.actions(), [], out)
        for tb in win.findChildren(QToolBar):
            if tb.window() is win and tb.isVisible():
                _walk_actions(tb.actions(), [], out)
    return out


def menus(a):
    """ui_menus: the menu and tool bar entries of a window, as text paths."""
    limit = a.get("limit", 500)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit is a whole number above 0")
    rows = [row for row, _act in _all_actions(a, acting=False)]
    under = a.get("under")
    if under:
        rows = [r for r in rows if r["path"] == under or r["path"].startswith(str(under) + " > ")]
    return {"entries": rows[:limit], "total": len(rows), "truncated": len(rows) > limit}


def menu(a):
    """ui_menu: choose one menu or tool bar entry by its path (or its objectName)."""
    path, name = a.get("path"), a.get("name")
    if bool(path) == bool(name):
        raise ValueError("say which entry: path ('Tools > Tool Plugins > My Tool', as ui_menus shows it) or name (its objectName)")
    hits = [(row, act) for row, act in _all_actions(a, acting=True)
            if (path and row["path"] == path) or (name and row.get("name") == name)]
    uniq = []
    for row, act in hits:
        if not any(act is u[1] for u in uniq):
            uniq.append((row, act))
    if not uniq:
        dlg = modal()
        if dlg is not None and not a.get("window"):
            raise ValueError("a modal dialog is open (%r) - answer it first (ui_answer_modal); the menus behind it cannot "
                             "be chosen" % (clean(dlg.windowTitle()) or type(dlg).__name__))
        raise ValueError("no menu entry %r - ui_menus lists them" % (path or name))
    if len(uniq) > 1:
        raise ValueError("%d entries match %r - nothing was chosen: %s"
                         % (len(uniq), path or name, "; ".join(r["path"] for r, _a in uniq[:8])))
    row, act = uniq[0]
    if not row["enabled"]:
        raise ValueError("that entry is disabled")
    if row.get("menu"):
        raise ValueError("that entry only opens a submenu - choose one of the entries under it")

    def after():
        return {"checked": bool(act.isChecked())} if act.isCheckable() else {}
    return _later({"chosen": row}, act.trigger, after, _wait_ms(a))
