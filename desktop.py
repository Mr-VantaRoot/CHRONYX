#!/usr/bin/env python3
"""Launch the bundled app in the platform's native webview window."""
import ctypes
import os
import json
import sys
import threading
import time
from urllib.request import urlopen

from server import Handler, LocalHTTPServer, notification_loop

service = None
_windows_mutex = None


def windows_mutex_is_existing(last_error):
    """Return whether CreateMutexW found the named desktop instance."""
    return last_error == 183  # ERROR_ALREADY_EXISTS


def acquire_windows_instance():
    """Keep a named mutex alive for this process to prevent duplicate windows."""
    global _windows_mutex
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    create_mutex.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    handle = create_mutex(None, False, 'Local\\CHRONYX.Desktop')
    if not handle:
        raise OSError(ctypes.get_last_error(), 'Could not create the CHRONYX instance mutex')
    if windows_mutex_is_existing(ctypes.get_last_error()):
        close_handle(handle)
        return False
    _windows_mutex = (kernel32, handle)
    return True

def start_or_attach_service():
    """Start one local API/scheduler, or attach to an existing CHRONYX one."""
    try:
        local_service = LocalHTTPServer(('127.0.0.1', 8765), Handler)
    except OSError as error:
        try:
            with urlopen('http://127.0.0.1:8765/api/events', timeout=1) as response:
                payload = json.load(response)
        except Exception as probe_error:
            raise RuntimeError(
                'Could not start CHRONYX because port 8765 is occupied by another service.'
            ) from probe_error
        if not isinstance(payload, list):
            raise RuntimeError('The process on port 8765 is not a CHRONYX service.') from error
        return None
    threading.Thread(target=local_service.serve_forever, daemon=True).start()
    threading.Thread(target=notification_loop, daemon=True).start()
    return local_service


def stop_service():
    global service
    if service:
        current_service = service
        service = None
        current_service.shutdown()
        current_service.server_close()


def run_windows():
    # pywebview uses the installed Microsoft Edge WebView2 runtime on Windows.
    try:
        import webview
        webview.create_window(
            'VANTA — Competition Tracker',
            f'http://127.0.0.1:8765/?v={time.time_ns()}',
            width=1360, height=900, min_size=(800, 600),
        )
        webview.start()
    finally:
        stop_service()


def run_linux():
    try:
        from gi import require_version
    except ImportError as error:
        raise SystemExit(
            f'CHRONYX could not import Python GObject bindings using {sys.executable}. '
            'Install the system Python GObject bindings and GTK 3 / WebKitGTK 4.1 '
            '(for example, python3-gobject, GTK 3, and WebKitGTK 4.1 packages).'
        ) from error
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


def main():
    global service
    if os.name == 'nt' and not acquire_windows_instance():
        ctypes.WinDLL('user32').MessageBoxW(
            None, 'CHRONYX is already running.', 'CHRONYX', 0x40,
        )
        return
    try:
        service = start_or_attach_service()
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    try:
        if os.name == 'nt':
            run_windows()
        else:
            run_linux()
    finally:
        stop_service()


if __name__ == '__main__':
    main()
