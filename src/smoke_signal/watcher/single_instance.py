"""Single-instance guard via a localhost socket.

The first Smoke Signal instance binds a fixed local port. A second launch
fails to bind, sends a SHOW message to the running instance (which pops the
dashboard window), and exits quietly. This prevents two watchers fighting
over the GPU lock and the SQLite state DB.
"""

import logging
import os
import socket
import threading
from typing import Callable

logger = logging.getLogger(__name__)

# Fixed, arbitrary loopback port. Only used on 127.0.0.1.
DEFAULT_PORT = 52718
_SHOW_MAGIC = b"SMOKE_SIGNAL_SHOW"


class SingleInstance:
    """Bind-or-signal single instance guard."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def acquire(self) -> bool:
        """Try to become the primary instance.

        Returns True if we are the first instance, False if another
        instance already holds the port.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if os.name == "nt":
                # Prevent another process from hijacking the port; Windows
                # already allows rebinding through TIME_WAIT by default.
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                # Allow rebinding while an old accepted connection sits in
                # TIME_WAIT (quit + relaunch within ~60s). Does NOT allow two
                # live listeners, so the guard still holds.
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", self.port))
            s.listen(2)
            self._sock = s
            return True
        except OSError:
            return False

    def notify_existing(self) -> bool:
        """Ask the already-running instance to show its window."""
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=2) as c:
                c.sendall(_SHOW_MAGIC)
            return True
        except OSError as e:
            logger.warning(f"Could not signal running instance: {e}")
            return False

    def listen(self, on_show: Callable[[], None]) -> None:
        """Start a background thread that pops the window on SHOW messages."""
        if self._sock is None:
            raise RuntimeError("listen() requires a successful acquire()")

        def loop() -> None:
            while True:
                try:
                    conn, _ = self._sock.accept()
                except OSError:
                    break  # socket closed — shutting down
                with conn:
                    try:
                        conn.settimeout(2)
                        data = conn.recv(64)
                    except OSError:
                        continue
                if data.startswith(_SHOW_MAGIC):
                    logger.info("Second launch detected — showing dashboard")
                    try:
                        on_show()
                    except Exception:
                        logger.exception("on_show callback failed")

        self._thread = threading.Thread(
            target=loop, daemon=True, name="single-instance"
        )
        self._thread.start()

    def release(self) -> None:
        """Close the socket (allows another instance to start)."""
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
