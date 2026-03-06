"""
snic_bee.uploader

Simple HTTP JSON uploader to a fixed IP server.
"""

import socket
import time

try:
    import ujson as json
except Exception:  # pragma: no cover (MicroPython vs CPython)
    import json  # type: ignore


class HTTPUploader:
    def __init__(
        self,
        server_ip,
        server_port,
        path="/",
        timeout_s=3,
        log_prefix="[snic_bee.upload]",
    ):
        self.server_ip = server_ip
        self.server_port = int(server_port)
        self.path = path if path.startswith("/") else "/" + path
        self.timeout_s = int(timeout_s)
        self.log_prefix = log_prefix

    def _log(self, msg):
        print("{} {}".format(self.log_prefix, msg))

    def post_json(self, payload):
        body = json.dumps(payload)
        if not isinstance(body, (bytes, bytearray)):
            body = body.encode("utf-8")

        addr = socket.getaddrinfo(self.server_ip, self.server_port, 0, socket.SOCK_STREAM)[0][-1]
        s = socket.socket()
        try:
            s.settimeout(self.timeout_s)
            s.connect(addr)

            req = (
                b"POST "
                + self.path.encode()
                + b" HTTP/1.1\r\n"
                + b"Host: "
                + self.server_ip.encode()
                + b"\r\n"
                + b"User-Agent: snic_bee/1.0\r\n"
                + b"Content-Type: application/json\r\n"
                + b"Connection: close\r\n"
                + b"Content-Length: "
                + str(len(body)).encode()
                + b"\r\n\r\n"
                + body
            )
            s.send(req)

            # Read a small part of response (status line) to detect server OK quickly.
            try:
                resp = s.recv(64) or b""
            except Exception:
                resp = b""

            ok = (b" 200 " in resp) or (b" 201 " in resp) or (b" 204 " in resp)
            if not ok and resp:
                self._log("non-2xx: {}".format(resp.split(b"\r\n")[0]))
            return ok
        except Exception as e:
            self._log("post failed: {}".format(e))
            return False
        finally:
            try:
                s.close()
            except Exception:
                pass


def utc_ms_fallback():
    # MicroPython often has no RTC set; use ticks_ms as best-effort timestamp.
    try:
        return time.time() * 1000
    except Exception:
        return time.ticks_ms()
