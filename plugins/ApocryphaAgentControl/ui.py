r"""MO2 Agent Control - the window commands (Qt only, no mobase, so the tests run this very code without MO2).

  ui_tree          what is on screen: the visible windows, the open modal dialog (its text and buttons), and the controls of
                   one window - buttons, checkboxes, radio buttons, edits, combo boxes, spin boxes, tab bars
  ui_click         presses one button, found by objectName, by its text, or by a path of names
  ui_answer_modal  presses a button of the open modal dialog, by role (accept, reject, yes, no ...) or by text
  ui_set           sets a checkbox / radio button, an edit, a combo box, a spin box or a tab bar, and reads the value back

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
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDialog,
                                 QDialogButtonBox, QDoubleSpinBox, QGroupBox, QLabel, QLineEdit, QMessageBox,
                                 QPlainTextEdit, QRadioButton, QSpinBox, QTabBar, QTabWidget, QTextEdit, QWidget)
except ImportError:  # MO2 before 2.5
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDialog,
                                 QDialogButtonBox, QDoubleSpinBox, QGroupBox, QLabel, QLineEdit, QMessageBox,
                                 QPlainTextEdit, QRadioButton, QSpinBox, QTabBar, QTabWidget, QTextEdit, QWidget)

ROLES = {-1: "invalid", 0: "accept", 1: "reject", 2: "destructive", 3: "action", 4: "help", 5: "yes", 6: "no",
         7: "reset", 8: "apply"}
KINDS = ("button", "checkbox", "radio", "edit", "text", "combo", "spin", "tabs", "label")
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
    if not name and not text:
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
