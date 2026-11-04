#!/usr/bin/python3
"""Launch the bundled app in the platform's native webview window."""
import os
import threading
import time
from http.server import ThreadingHTTPServer

from server import Handler, notification_loop

try:
    service = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    threading.Thread(target=service.serve_forever, daemon=True).start()
    threading.Thread(target=notification_loop, daemon=True).start()
except OSError:
    # A prior VANTA instance already owns the loopback service.
    service = None


def stop_service():
    if service:
        service.shutdown()
        service.server_close()


def run_windows():
    # pywebview uses the installed Microsoft Edge WebView2 runtime on Windows.
    import webview
    webview.create_window(
        'VANTA — Competition Tracker',
        f'http://127.0.0.1:8765/?v={time.time_ns()}',
        width=1360, height=900, min_size=(800, 600),
    )
    try:
        webview.start()
    finally:
        stop_service()


def run_linux():
    from gi import require_version
    require_version('Gtk', '3.0')
    require_version('WebKit2', '4.1')
    from gi.repository import Gtk, WebKit2

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
            self.window.set_icon_from_file(os.path.join(os.path.dirname(__file__), 'public', 'vanta.svg'))
            view = WebKit2.WebView()
            view.set_vexpand(True)
            view.set_hexpand(True)
            view.load_uri(f'http://127.0.0.1:8765/?v={time.time_ns()}')
            self.window.add(view)
            self.window.show_all()

        def do_shutdown(self):
            stop_service()
            Gtk.Application.do_shutdown(self)

    raise SystemExit(Vanta().run(None))


if __name__ == '__main__':
    if os.name == 'nt':
        run_windows()
    else:
        run_linux()
