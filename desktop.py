#!/usr/bin/python3
"""Lightweight GTK desktop window around VANTA's bundled local interface."""
import threading
import time
from http.server import ThreadingHTTPServer

from gi import require_version
require_version('Gtk', '3.0')
require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2

from server import Handler, notification_loop

try:
    service = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    threading.Thread(target=service.serve_forever, daemon=True).start()
    threading.Thread(target=notification_loop, daemon=True).start()
except OSError:
    # A prior VANTA instance already owns the loopback service.
    service = None


class Vanta(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.vanta.CompetitionTracker')
        self.window = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title='VANTA — Competition Tracker')
        self.window.set_default_size(1360, 900)
        self.window.set_size_request(800, 600)
        self.window.set_icon_from_file(__file__.rsplit('/', 1)[0] + '/public/vanta.svg')
        view = WebKit2.WebView()
        view.set_vexpand(True)
        view.set_hexpand(True)
        view.load_uri(f'http://127.0.0.1:8765/?v={time.time_ns()}')
        self.window.add(view)
        self.window.show_all()

    def do_shutdown(self):
        if service:
            service.shutdown()
            service.server_close()
        Gtk.Application.do_shutdown(self)


if __name__ == '__main__':
    raise SystemExit(Vanta().run(None))
