r"""MO2 Agent Control - lets scripts, tools and AI agents operate a running Mod Organizer 2 without screen control.

On load it opens a command channel on 127.0.0.1 ONLY (a random port, never another interface) with a fresh random token,
and writes both to plugins\data\ApocryphaAgentControl\channel.json inside this MO2 instance - so only a program that can
read this instance's files can talk to it. The client is tools\mo2-ctl.py; docs\PROTOCOL.md describes the JSON lines it
sends, for anyone writing their own. What a request may do is decided in core.py (token, command list, the in-use check
for writes, backups); this file is MO2's side: its API, its window's profile box and the socket - all on MO2's own GUI
thread, so every API call is made where MO2 expects it.

Other MO2 plugins can offer their own commands (the `call` command): they put a handler into the shared module
`apocrypha_agent_registry` (sys.modules), `handlers[<plugin name>] = fn(action, args) -> JSON-able result`. MO2 Modlist
Manager does this when it is installed; nothing here depends on it.
"""
import ctypes
import json
import os
import re
import secrets
import sys
import time

import mobase

try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QIcon
    from PyQt6.QtNetwork import QHostAddress, QTcpServer
    from PyQt6.QtWidgets import QApplication, QComboBox, QMainWindow, QMessageBox
    LOCALHOST = QHostAddress.SpecialAddress.LocalHost
except ImportError:  # MO2 before 2.5
    from PyQt5.QtCore import QTimer
    from PyQt5.QtGui import QIcon
    from PyQt5.QtNetwork import QHostAddress, QTcpServer
    from PyQt5.QtWidgets import QApplication, QComboBox, QMainWindow, QMessageBox
    LOCALHOST = QHostAddress.LocalHost

from . import core

__version__ = "1.0.0"    # issued by version-gate.ps1; never typed by hand
PLUGIN_NAME = "MO2 Agent Control"
DATA_NAME = "ApocryphaAgentControl"       # the folder name under plugins\ and plugins\data\ (clients find channel.json there)
REGISTRY = "apocrypha_agent_registry"
MAX_REQUEST = 1 << 20

# ---------------------------------------------------------------------------------------------------------------------
# Languages: TR("KEY", "English") reads translations\<language>.txt beside this file ($KEY<TAB>text, UTF-16LE with a BOM).
# English is the default and the fallback. The language is MO2's own (ModOrganizer.ini, [Settings] language). Command
# replies stay English (core.py): tools read them.
# ---------------------------------------------------------------------------------------------------------------------
_LANG_FILES = {"en": "english", "ja": "japanese", "ko": "korean", "zh": "chinese", "ru": "russian", "de": "german",
               "fr": "french", "es": "spanish", "it": "italian", "pl": "polish", "cs": "czech"}
STRINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
_STRINGS = {}


def mo2_language(base_dir):
    """MO2's own language code from ModOrganizer.ini ([Settings] language=de_DE), or "en"."""
    try:
        with open(os.path.join(base_dir, "ModOrganizer.ini"), encoding="utf-8-sig", errors="replace") as f:
            m = re.search(r"(?mi)^language\s*=\s*([A-Za-z_\-]+)", f.read())
        if m:
            return m.group(1)
    except (OSError, TypeError):
        pass
    return "en"


def load_strings(code):
    """Load the strings for a language code ("de", "de_DE", "zh_CN"); English or an unknown code loads nothing."""
    _STRINGS.clear()
    name = _LANG_FILES.get((code or "en").replace("-", "_").split("_")[0].lower(), "english")
    if name == "english":
        return name
    try:
        with open(os.path.join(STRINGS_DIR, name + ".txt"), "rb") as f:
            raw = f.read()
    except OSError:
        return "english"
    text = raw[2:].decode("utf-16-le", "replace") if raw[:2] == b"\xff\xfe" else raw.decode("utf-8-sig", "replace")
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith("$") and "\t" in line:
            k, _, v = line.partition("\t")
            _STRINGS[k[1:].strip()] = v.replace("\\n", "\n")
    return name


def TR(key, english, **kw):
    text = _STRINGS.get(key, english)
    if not kw:
        return text
    try:
        return text.format(**kw)
    except (KeyError, IndexError, ValueError):
        return english.format(**kw)


# ---- MO2's side, as core.Dispatcher sees it ------------------------------------------------------------------------------
class Mo2:
    def __init__(self, organizer):
        self.o = organizer

    def base_path(self):
        return self.o.basePath()

    def profile_name(self):
        return self.o.profileName()

    def profile_dir(self):
        return self.o.profilePath()

    def game_name(self):
        try:
            return self.o.managedGame().gameName()
        except Exception:  # noqa: BLE001
            return ""

    def profiles(self):
        root = os.path.dirname(self.o.profilePath())
        return sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))

    def mods(self):
        ml = self.o.modList()
        out = []
        for name in ml.allModsByProfilePriority():
            st = ml.state(name)
            out.append({"name": name, "active": bool(st & mobase.ModState.ACTIVE),
                        "separator": name.endswith("_separator")})
        return out

    def plugins(self):
        pl = self.o.pluginList()
        names = sorted(pl.pluginNames(), key=lambda n: pl.priority(n))
        return [{"name": n, "active": pl.state(n) == mobase.PluginState.ACTIVE, "origin": pl.origin(n)} for n in names]

    def overwrite_path(self):
        return self.o.overwritePath()

    def executables(self):
        out = []
        try:
            import configparser
            cp = configparser.RawConfigParser(strict=False)
            cp.read(os.path.join(self.o.basePath(), "ModOrganizer.ini"), encoding="utf-8")
            sec = cp["customExecutables"] if cp.has_section("customExecutables") else {}
            for i in range(1, int(sec.get("size", "0")) + 1):
                out.append({"title": sec.get("%d\\title" % i, ""), "binary": sec.get("%d\\binary" % i, "")})
        except Exception:  # noqa: BLE001
            pass
        return out

    def select_profile(self, name):
        box = None
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QMainWindow):
                box = w.findChild(QComboBox, "profileBox")
                if box is not None:
                    break
        if box is None:
            raise RuntimeError("MO2's profile box was not found")
        i = box.findText(name)
        if i < 0:
            raise ValueError("the profile box has no %r" % name)
        box.setCurrentIndex(i)          # MO2's own handler switches the profile, exactly as a pick in the box does
        if self.o.profileName() != name:
            raise RuntimeError("MO2 did not switch to %r (still %r)" % (name, self.o.profileName()))

    def set_mods(self, names, active):
        self.o.modList().setActive(names, active)

    def set_plugins(self, names, active):
        """MO2 writes plugins.txt LATE (setState showed active:false, but plugins.txt kept the plugin ticked and the next
        refresh read it back as active). So the state is set in memory AND written into the profile's plugins.txt the
        way MO2 writes it ('*' = active), then MO2 re-reads the file (refresh without saving) and the result is
        checked. core.py backed the file up first."""
        state = mobase.PluginState.ACTIVE if active else mobase.PluginState.INACTIVE
        pl = self.o.pluginList()
        for n in names:
            pl.setState(n, state)
        path = os.path.join(self.o.profilePath(), "plugins.txt")
        with open(path, encoding="utf-8-sig", newline="") as f:
            text = f.read()
        eol = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines()
        want = {n.lower() for n in names}
        seen = set()
        out = []
        for ln in lines:
            bare = ln[1:] if ln.startswith("*") else ln
            if not ln.startswith("#") and bare.strip().lower() in want:
                seen.add(bare.strip().lower())
                ln = ("*" + bare) if active else bare
            out.append(ln)
        for n in names:
            if n.lower() not in seen:
                out.append(("*" + n) if active else n)
        tmp = path + ".agent-tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(eol.join(out) + eol)
        os.replace(tmp, path)
        # memory and file now agree; MO2 re-reads the file (refresh without saving - its rebuild is asynchronous, so the
        # state is not read back here: a later `plugins` read shows it)
        self.o.refresh(False)
        with open(path, encoding="utf-8-sig") as f:
            on = {ln[1:].strip().lower() for ln in f if ln.startswith("*")}
        wrong = [n for n in names if (n.lower() in on) != active]
        if wrong:
            raise RuntimeError("plugins.txt does not hold %s as %s after the write" % (", ".join(wrong), "active" if active else "inactive"))

    def refresh(self, save):
        self.o.refresh(save)

    def run(self, target, args, cwd, profile):
        handle = self.o.startApplication(target, list(args), cwd, profile)
        pid = ctypes.windll.kernel32.GetProcessId(ctypes.c_void_p(int(handle))) if handle else 0
        if not pid:
            raise RuntimeError("MO2 did not start %r" % target)
        return {"started": target, "pid": pid}

    def extensions(self):
        reg = sys.modules.get(REGISTRY)
        return list(getattr(reg, "handlers", {}) or {}) if reg else []

    def call_plugin(self, plugin, action, args):
        reg = sys.modules.get(REGISTRY)
        fn = getattr(reg, "handlers", {}).get(plugin) if reg else None
        if fn is None:
            raise RuntimeError("%s has no command handler loaded in this MO2 (info lists the extensions)" % plugin)
        return fn(action, args)


# ---- is someone using MO2 right now? -------------------------------------------------------------------------------------
def idle_minutes(activity_file):
    """(minutes since the last keyboard/mouse input, where that came from). An activity file - a JSON file another tool
    keeps up to date with {"last_input_epoch": ..., "alive_epoch": ...} - is used while it is fresh (written in the last
    3 minutes): such a tool can tell a person's input from a script's. Otherwise Windows' own idle clock."""
    if activity_file:
        try:
            with open(activity_file, encoding="utf-8") as f:
                d = json.load(f)
            alive = float(d.get("alive_epoch", d.get("watcher_alive_epoch")))
            last = float(d.get("last_input_epoch", d.get("last_real_input_epoch")))
            if time.time() - alive < 180:
                return (time.time() - last) / 60.0, "activity file"
        except Exception:  # noqa: BLE001
            pass

    class LII(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    li = LII(ctypes.sizeof(LII), 0)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
        return ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 60000.0, "Windows' idle clock"
    return None, "unknown"


def in_use(check_on, minutes, activity_file):
    """(in_use, why): MO2's window is in front AND there was input within `minutes`."""
    if not check_on:
        return False, "the in-use check is turned off"
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    pid = ctypes.c_ulong(0)
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value != os.getpid():
        return False, "MO2 is not the window in front"
    idle, src = idle_minutes(activity_file)
    if idle is not None and idle < minutes:
        return True, "MO2 is in front and the last input was %.1f min ago (%s)" % (idle, src)
    return False, "MO2 is in front but idle %s" % ("unknown" if idle is None else "%.0f min" % idle)


# ---- the plugin ----------------------------------------------------------------------------------------------------------
class AgentControl(mobase.IPluginTool):
    def __init__(self):
        super().__init__()
        self._org = None
        self._server = None
        self._sockets = []
        self._parent = None
        self._dispatcher = None

    def init(self, organizer):
        self._org = organizer
        load_strings(mo2_language(organizer.basePath()))
        QTimer.singleShot(0, self._start)
        return True

    def _setting(self, key, default):
        try:
            v = self._org.pluginSetting(PLUGIN_NAME, key)
        except Exception:  # noqa: BLE001
            return default
        return default if v is None else v

    def _presence(self):
        try:
            minutes = float(self._setting("in_use_minutes", 5))
        except (TypeError, ValueError):
            minutes = 5.0
        return in_use(bool(self._setting("refuse_writes_while_in_use", True)), minutes,
                      str(self._setting("activity_file", "") or "").strip())

    def _data(self):
        d = os.path.join(self._org.basePath(), "plugins", "data", DATA_NAME)
        os.makedirs(d, exist_ok=True)
        return d

    def _log(self, text):
        try:
            with open(os.path.join(self._data(), "log.txt"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")
        except OSError:
            pass

    def _start(self):
        token = secrets.token_hex(32)
        self._dispatcher = core.Dispatcher(Mo2(self._org), token, os.path.join(self._data(), "backups"), self._presence,
                                           self._log, __version__)
        self._server = QTcpServer()
        if not self._server.listen(QHostAddress(LOCALHOST), 0):
            self._log("could not listen on 127.0.0.1: %s" % self._server.errorString())
            return
        self._server.newConnection.connect(self._accept)
        channel = {"host": "127.0.0.1", "port": int(self._server.serverPort()), "token": token, "pid": os.getpid(),
                   "instance": self._org.basePath(), "started": time.time(), "version": __version__,
                   "protocol": core.PROTOCOL}
        path = os.path.join(self._data(), "channel.json")
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(channel, f)
        os.replace(path + ".tmp", path)
        self._log("%s %s listening on 127.0.0.1:%d (pid %d)" % (PLUGIN_NAME, __version__, channel["port"], channel["pid"]))

    def _accept(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            if not sock.peerAddress().isLoopback():
                self._log("refused a connection from %s" % sock.peerAddress().toString())
                sock.abort()
                continue
            buf = bytearray()
            self._sockets.append(sock)

            def ready(sock=sock, buf=buf):
                buf.extend(bytes(sock.readAll()))
                if len(buf) > MAX_REQUEST:
                    sock.abort()
                    return
                if b"\n" not in buf:
                    return
                line = bytes(buf[:buf.index(b"\n")])
                resp = self._dispatcher.handle(line)
                sock.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
                sock.flush()
                sock.disconnectFromHost()

            sock.readyRead.connect(ready)
            sock.disconnected.connect(lambda sock=sock: (self._sockets.remove(sock) if sock in self._sockets else None,
                                                         sock.deleteLater()))

    # ---- mobase.IPluginTool
    def name(self):
        return PLUGIN_NAME

    def author(self):
        return "ApocryphaRealm"

    def description(self):
        return TR("AC_Description", "A command channel on this computer only (127.0.0.1, a new secret token each session) "
                                    "that lets scripts, tools and AI agents operate MO2 without clicking on its window.")

    def version(self):
        major, minor, patch = (int(x) for x in __version__.split("."))
        return mobase.VersionInfo(major, minor, patch, mobase.ReleaseType.FINAL)

    def settings(self):
        return [
            mobase.PluginSetting("refuse_writes_while_in_use",
                                 TR("AC_SetRefuse", "Refuse commands that change anything while you are using MO2 (its "
                                                    "window in front, keyboard or mouse used recently). Reading is "
                                                    "always allowed."), True),
            mobase.PluginSetting("in_use_minutes",
                                 TR("AC_SetMinutes", "How many minutes after your last keyboard or mouse input MO2 still "
                                                     "counts as in use."), 5),
            mobase.PluginSetting("activity_file",
                                 TR("AC_SetActivity", "Optional: a JSON file another tool keeps up to date with your last "
                                                      "real input (last_input_epoch, alive_epoch). Empty uses Windows' "
                                                      "idle clock."), ""),
        ]

    def isActive(self):
        return True

    def displayName(self):
        return TR("AC_DisplayName", "Agent Control")

    def tooltip(self):
        return TR("AC_Tooltip", "Shows whether the command channel is listening")

    def icon(self):
        return QIcon()

    def setParentWidget(self, widget):
        self._parent = widget

    def display(self):
        listening = self._server is not None and self._server.isListening()
        if listening:
            busy, why = self._presence()
            text = TR("AC_Listening", "Listening on 127.0.0.1:{port} for mo2-ctl and other clients.\n\nChannel file:\n{path}",
                      port=self._server.serverPort(), path=os.path.join(self._data(), "channel.json"))
            text += "\n\n" + (TR("AC_CheckOn", "Changes are refused while you are using MO2.") if bool(self._setting(
                "refuse_writes_while_in_use", True)) else TR("AC_CheckOff", "The in-use check is off: changes are always accepted."))
        else:
            text = TR("AC_NotListening", "Not listening - see the log in plugins\\data\\{name}\\log.txt.", name=DATA_NAME)
        QMessageBox.information(self._parent, TR("AC_DisplayName", "Agent Control"), text)


def createPlugin():
    return AgentControl()


# --- fault handling: Python frames of every thread into plugins\data\faults.log if MO2 dies in C++ under one of our slots ---
def _arm_faulthandler():
    try:
        import faulthandler
        if faulthandler.is_enabled():
            return
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # ...\plugins
        path = os.path.join(here, "data", "faults.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fh = open(path, "a", encoding="utf-8")
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S") + " faulthandler armed by " + DATA_NAME + "\n")
        fh.flush()
        globals()["_FAULT_LOG_HANDLE"] = fh
        faulthandler.enable(file=fh, all_threads=True)
    except Exception:  # noqa: BLE001
        pass


_arm_faulthandler()
