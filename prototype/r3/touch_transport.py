"""Session-local, ordered evdev packets. This module never injects SDL events."""

import socket
import struct
import time

PACKET = struct.Struct("!iidffq")
KINDS = {"heartbeat": 0, "down": 1, "move": 2, "up": 3, "cancel": 4}


class TouchTransport:
    def __init__(self, directory, clock=time.monotonic):
        self.directory = directory
        self.clock = clock
        self.socket = None
        self.retry_at = 0
        self.pulse_at = 0
        self.contact = None
        self.serial = 0
        self.point = (0, 0)
        self.sent = 0

    def close(self):
        if self.socket:
            self.socket.close()
        self.socket = None
        self.contact = None

    def packet(self, kind):
        if not self.socket:
            return
        try:
            self.socket.sendall(PACKET.pack(
                0x53545331, KINDS[kind], self.clock(), *self.point, self.serial))
            self.sent += 1
        except OSError:
            self.close()

    def tick(self):
        now = self.clock()
        if not self.socket and now >= self.retry_at:
            self.retry_at = now + .5
            try:
                port = int((self.directory / "touch-port.txt").read_text())
                if not 1024 <= port <= 65535:
                    return
                self.socket = socket.create_connection(("127.0.0.1", port), timeout=.02)
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.contact = None
                self.packet("cancel")
            except (OSError, ValueError):
                self.close()
        if self.socket and now >= self.pulse_at:
            self.packet("heartbeat")
            self.pulse_at = now + .25

    def cancel(self):
        self.contact = None
        self.packet("cancel")

    def actions(self, actions, focused):
        # Cancellation and pad takeover win the whole poll, including a queued UP.
        if not focused or any(a[0] in ("cancel", "button") for a in actions):
            if actions:
                self.cancel()
            return
        for action in actions:
            kind = action[0]
            if kind == "down":
                if not self.socket:
                    continue
                self.serial += 1
                self.contact = action[1]
                self.point = action[2:4]
                self.packet(kind)
            elif kind in ("move", "up") and self.contact == action[1]:
                if kind == "move":
                    self.point = action[2:4]
                self.packet(kind)
                if kind == "up":
                    self.contact = None
