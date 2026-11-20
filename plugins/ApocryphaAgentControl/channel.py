r"""MO2 Agent Control - the loopback socket (Qt only, no mobase, so the tests run this very code without MO2).

A QTcpServer on 127.0.0.1, a random free port. One request line in, one reply line out, then the connection closes
(docs\PROTOCOL.md). Everything runs on the thread that owns the server - MO2's GUI thread - so every command is carried
out where MO2 expects its API and its widgets to be used.

Two things follow from living on the GUI thread, and both are relied on:
  - a modal dialog (QDialog.exec, QMessageBox.exec) runs a nested event loop on that same thread, and a nested loop
    delivers socket notifications like any other event - so requests are still answered while a dialog is open
    (tests\test_ui_widgets.py proves it against this code);
  - a reply may be written LATER than the request was read: a window command whose button press opens a dialog does not
    return until the dialog is closed, so the dispatcher is given `send` and may call it after `handle` has returned.
"""
import json

try:
    from PyQt6.QtNetwork import QHostAddress, QTcpServer
    LOCALHOST = QHostAddress.SpecialAddress.LocalHost
except ImportError:  # MO2 before 2.5
    from PyQt5.QtNetwork import QHostAddress, QTcpServer
    LOCALHOST = QHostAddress.LocalHost

MAX_REQUEST = 1 << 20


class Channel:
    """dispatcher: core.Dispatcher (handle(line, reply)). log(text): one line to the plugin's log."""

    def __init__(self, dispatcher, log=lambda s: None):
        self.dispatcher, self.log = dispatcher, log
        self._server = None
        self._sockets = []

    def listen(self):
        """Starts listening; returns the port, or 0 (error() says why)."""
        self._server = QTcpServer()
        if not self._server.listen(QHostAddress(LOCALHOST), 0):
            return 0
        self._server.newConnection.connect(self._accept)
        return int(self._server.serverPort())

    def error(self):
        return self._server.errorString() if self._server is not None else "not started"

    def listening(self):
        return self._server is not None and self._server.isListening()

    def port(self):
        return int(self._server.serverPort()) if self._server is not None else 0

    def close(self):
        if self._server is not None:
            self._server.close()

    def _accept(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            if not sock.peerAddress().isLoopback():
                self.log("refused a connection from %s" % sock.peerAddress().toString())
                sock.abort()
                continue
            self._sockets.append(sock)
            self._serve(sock)

    def _serve(self, sock):
        buf = bytearray()
        state = {"read": False, "sent": False}

        def send(resp):
            if state["sent"]:
                return
            state["sent"] = True
            try:
                sock.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
                sock.flush()
                sock.disconnectFromHost()
            except RuntimeError:        # the client gave up and the socket is gone
                pass

        def ready():
            if state["read"]:
                return                  # one request per connection; anything after the first line is ignored
            buf.extend(bytes(sock.readAll()))
            if len(buf) > MAX_REQUEST:
                sock.abort()
                return
            if b"\n" not in buf:
                return
            state["read"] = True
            resp = self.dispatcher.handle(bytes(buf[:buf.index(b"\n")]), send)
            if resp is not None:        # None: the command answers through send, later
                send(resp)

        def gone():
            if sock in self._sockets:
                self._sockets.remove(sock)
            sock.deleteLater()

        sock.readyRead.connect(ready)
        sock.disconnected.connect(gone)
