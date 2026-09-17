"""Local YOLO inference service for the XIAO ESP32-S3 Sense camera."""

import threading
import time
from dataclasses import dataclass, field
from typing import Iterator
from urllib.error import URLError
from urllib.request import urlopen

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from ultralytics import YOLO


FRAME_SIZES = {
    "160x120": (160, 120),
    "320x240": (320, 240),
}
DEFAULT_DEVICE_URL = "http://192.168.1.11"


@dataclass
class EngineState:
    device_url: str = DEFAULT_DEVICE_URL
    frame_size: str = "160x120"
    confidence: float = 0.35
    model: YOLO | None = None
    model_error: str = ""
    last_detections: list[dict] = field(default_factory=list)
    last_frame_at: float = 0.0
    last_error: str = ""


state = EngineState()
model_lock = threading.Lock()
capture_lock = threading.Lock()
app = FastAPI(title="Glass Local Vision Engine")


class EngineConfig(BaseModel):
    device_url: str = Field(default=DEFAULT_DEVICE_URL)
    frame_size: str = Field(default="160x120")
    confidence: float = Field(default=0.35, ge=0.05, le=0.95)


def normalized_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = "http://" + value
    return value


def load_model() -> YOLO:
    if state.model is not None:
        return state.model
    with model_lock:
        if state.model is None:
            try:
                # Ultralytics downloads this small local weight once when absent.
                state.model = YOLO("yolo11n.pt")
                state.model_error = ""
            except Exception as exc:
                state.model_error = str(exc)
                raise RuntimeError("YOLO model load failed: %s" % exc) from exc
    return state.model


def rgb565_to_bgr(raw: bytes, frame_size: str) -> np.ndarray:
    width, height = FRAME_SIZES[frame_size]
    expected = width * height * 2
    if len(raw) != expected:
        raise ValueError("expected %d bytes, received %d" % (expected, len(raw)))
    pixels = np.frombuffer(raw, dtype=">u2").reshape(height, width)
    red = ((pixels >> 11) & 0x1F).astype(np.uint8) << 3
    green = ((pixels >> 5) & 0x3F).astype(np.uint8) << 2
    blue = (pixels & 0x1F).astype(np.uint8) << 3
    return np.dstack((blue, green, red))


def capture_frame() -> np.ndarray:
    url = normalized_url(state.device_url) + "/frame.raw?ts=%d" % int(time.time() * 1000)
    try:
        with capture_lock, urlopen(url, timeout=15) as response:
            raw = response.read()
        image = rgb565_to_bgr(raw, state.frame_size)
        state.last_frame_at = time.time()
        state.last_error = ""
        return image
    except (URLError, OSError, ValueError) as exc:
        state.last_error = str(exc)
        raise RuntimeError("camera fetch failed: %s" % exc) from exc


def detect(image: np.ndarray) -> tuple[np.ndarray, list[dict]]:
    model = load_model()
    with model_lock:
        result = model(image, imgsz=320, conf=state.confidence, verbose=False)[0]
    detections = []
    for box in result.boxes:
        class_id = int(box.cls[0])
        x1, y1, x2, y2 = [round(float(value), 1) for value in box.xyxy[0].tolist()]
        detections.append({
            "label": result.names[class_id],
            "confidence": round(float(box.conf[0]), 3),
            "box": [x1, y1, x2, y2],
        })
    state.last_detections = detections
    return result.plot(), detections


def jpeg_response(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return encoded.tobytes()


def current_status() -> dict:
    return {
        "device_url": normalized_url(state.device_url),
        "frame_size": state.frame_size,
        "confidence": state.confidence,
        "model": "yolo11n.pt",
        "model_ready": state.model is not None,
        "model_error": state.model_error,
        "last_frame_at": state.last_frame_at or None,
        "last_error": state.last_error,
        "detections": state.last_detections,
    }


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse("glass/engine/web/index.html")


@app.get("/api/status")
def status():
    return current_status()


@app.post("/api/config")
def configure(config: EngineConfig):
    if config.frame_size not in FRAME_SIZES:
        raise HTTPException(status_code=400, detail="frame_size must be 160x120 or 320x240")
    state.device_url = normalized_url(config.device_url)
    state.frame_size = config.frame_size
    state.confidence = config.confidence
    state.last_error = ""
    return current_status()


@app.post("/api/detect")
def detect_once():
    try:
        annotated, detections = detect(capture_frame())
        return {"detections": detections, "image_url": "/api/frame.jpg?ts=%d" % int(time.time() * 1000)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/frame.jpg")
def frame_jpeg():
    try:
        annotated, _ = detect(capture_frame())
        return StreamingResponse(iter([jpeg_response(annotated)]), media_type="image/jpeg")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/stream")
def stream() -> StreamingResponse:
    def frames() -> Iterator[bytes]:
        while True:
            try:
                annotated, _ = detect(capture_frame())
                jpeg = jpeg_response(annotated)
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
            except RuntimeError as exc:
                state.last_error = str(exc)
                break

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )
