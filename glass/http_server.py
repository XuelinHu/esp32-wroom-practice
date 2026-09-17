"""Small HTTP server for the combined camera and voice device."""

import json
import os
import socket
import time

try:
    import _thread
except ImportError:
    _thread = None


class GlassHTTPServer:
    def __init__(self, camera, recorder, storage, port=80):
        self.camera = camera
        self.recorder = recorder
        self.storage = storage
        self.port = port
        self.server = None
        self.running = False
        self.stream_active = False
        self.started = time.time()

    def _response(self, client, status, content_type, body):
        header = (
            "HTTP/1.1 %s\r\n"
            "Content-Type: %s\r\n"
            "Content-Length: %d\r\n"
            "Cache-Control: no-store\r\n"
            "Connection: close\r\n\r\n"
        ) % (status, content_type, len(body))
        client.sendall(header.encode() + body)

    def _json(self, client, value, status="200 OK"):
        self._response(client, status, "application/json", json.dumps(value).encode())

    def _sync_storage(self):
        if self.storage.mount():
            self.recorder.set_record_dir(self.storage.recordings_dir())

    def _parse(self, client):
        data = client.recv(1024)
        if not data:
            return None, None
        line = data.split(b"\r\n", 1)[0].decode("utf-8", "ignore")
        parts = line.split()
        if len(parts) < 2:
            return None, None
        return parts[0], parts[1]

    def _safe_name(self, name):
        return (
            name and name == name.split("/")[-1] and
            ".." not in name and name.lower().endswith(".wav")
        )

    def _serve_file(self, client, path, content_type):
        try:
            size = os.stat(path)[6]
            header = (
                "HTTP/1.1 200 OK\r\nContent-Type: %s\r\n"
                "Content-Length: %d\r\nCache-Control: no-store\r\n"
                "Connection: close\r\n\r\n"
            ) % (content_type, size)
            client.sendall(header.encode())
            with open(path, "rb") as source:
                while True:
                    chunk = source.read(2048)
                    if not chunk:
                        break
                    client.sendall(chunk)
            return True
        except Exception:
            return False

    def _stream(self, client):
        if self.stream_active:
            self._response(client, "409 Conflict", "text/plain", b"stream busy")
            return
        self.stream_active = True
        try:
            header = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
                "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
            )
            client.sendall(header.encode())
            while self.running:
                frame = self.camera.capture()
                if not frame:
                    continue
                part = (
                    ("--frame\r\nContent-Type: %s\r\n" % self.camera.content_type()).encode()
                    + ("Content-Length: %d\r\n\r\n" % len(frame)).encode()
                )
                client.sendall(part)
                client.sendall(frame)
                client.sendall(b"\r\n")
        except Exception:
            pass
        finally:
            self.stream_active = False

    def _handle(self, client):
        method, path = self._parse(client)
        if not method:
            return
        route = path.split("?", 1)[0]
        if route in ("/", "/index.html"):
            if not self._serve_file(client, "/web/index.html", "text/html; charset=utf-8"):
                self._response(client, "500 Internal Server Error", "text/plain", b"missing /web/index.html")
        elif route == "/stream":
            self._stream(client)
        elif route == "/capture":
            frame = self.camera.capture()
            if frame:
                self._response(client, "200 OK", self.camera.content_type(), frame)
            else:
                self._response(client, "503 Service Unavailable", "text/plain", b"capture failed")
        elif route == "/frame.raw":
            frame = self.camera.capture_raw()
            if frame:
                self._response(client, "200 OK", "application/octet-stream", frame)
            else:
                self._response(client, "503 Service Unavailable", "text/plain", b"capture failed")
        elif route == "/status":
            self._json(client, {
                "camera": self.camera.status(),
                "voice": self.recorder.status(),
                "sd": self.storage.status(),
            })
        elif route == "/api/voice/status":
            self._json(client, self.recorder.status())
        elif route == "/api/voice/start" and method == "POST":
            self._sync_storage()
            self._json(client, self.recorder.start())
        elif route == "/api/voice/stop" and method == "POST":
            self._json(client, self.recorder.stop())
        elif route == "/api/recordings":
            self._json(client, self.recorder.recordings())
        elif route.startswith("/recordings/"):
            name = route[len("/recordings/"):]
            if self._safe_name(name) and name in self.recorder.recordings():
                if not self._serve_file(client, self.recorder.recording_path(name), "audio/wav"):
                    self._response(client, "500 Internal Server Error", "text/plain", b"read failed")
            else:
                self._response(client, "404 Not Found", "text/plain", b"not found")
        elif route == "/api/camera":
            query = path.split("?", 1)[1] if "?" in path else ""
            params = {}
            for item in query.split("&"):
                if "=" in item:
                    key, value = item.split("=", 1)
                    params[key] = value
            if "size" in params:
                self.camera.set_framesize(params["size"])
            self._json(client, self.camera.status())
        elif route == "/api/sd/status":
            self._sync_storage()
            self._json(client, self.storage.status())
        elif route == "/api/sd/test" and method == "POST":
            self._sync_storage()
            self._json(client, self.storage.test())
        elif route == "/api/sd/files":
            self._sync_storage()
            self._json(client, self.storage.files())
        else:
            self._response(client, "404 Not Found", "text/plain", b"not found")

    def _client_worker(self, client):
        try:
            self._handle(client)
        except Exception as exc:
            print("HTTP_CLIENT_ERROR", exc)
        finally:
            client.close()

    def run(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("0.0.0.0", self.port))
        self.server.listen(2)
        self.server.settimeout(1)
        self.running = True
        print("WEB_SERVER_STARTED port=%d" % self.port)
        while self.running:
            try:
                client, _ = self.server.accept()
                if _thread is not None:
                    _thread.start_new_thread(self._client_worker, (client,))
                else:
                    self._client_worker(client)
            except OSError:
                pass
            except KeyboardInterrupt:
                break
        self.stop()

    def stop(self):
        self.running = False
        if self.server is not None:
            self.server.close()
            self.server = None
