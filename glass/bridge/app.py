"""Laptop bridge for Arduino XIAO camera JPEG and onboard PDM audio."""

import asyncio
import threading
import time
import wave
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
RECORDINGS = ROOT / "recordings"
SAMPLE_RATE = 16000
CAMERA_RESOLUTIONS = {"qvga", "vga", "svga", "xga", "hd", "uxga", "qxga"}


class CameraResolutionRequest(BaseModel):
    resolution: str


class State:
    camera_connected = False
    audio_connected = False
    latest_bgr = None
    frame_id = 0
    last_frame_at = 0.0
    detections = []
    error = ""
    recording = False
    audio_chunks = []
    last_recording = ""
    sd_status = "Awaiting device response"
    device_camera_socket = None
    device_audio_socket = None
    audio_packets = 0
    audio_bytes = 0
    last_audio_at = 0.0
    camera_resolution = "1024x768"
    camera_status = "Camera ready"
    model = None


state = State()
frame_lock = threading.Lock()
model_lock = threading.Lock()
app = FastAPI(title="Glass Arduino Bridge")


def get_model():
    if state.model is None:
        with model_lock:
            if state.model is None:
                state.model = YOLO("yolo11n.pt")
    return state.model


def detect(bgr):
    result = get_model()(bgr, imgsz=320, conf=0.35, verbose=False)[0]
    detections = []
    for box in result.boxes:
        class_id = int(box.cls[0])
        detections.append({
            "label": result.names[class_id],
            "confidence": round(float(box.conf[0]), 3),
        })
    state.detections = detections
    return result.plot()


def status():
    return {
        "camera_connected": state.camera_connected,
        "audio_connected": state.audio_connected,
        "last_frame_at": state.last_frame_at or None,
        "detections": state.detections,
        "recording": state.recording,
        "last_recording": state.last_recording,
        "sd_status": state.sd_status,
        "audio_packets": state.audio_packets,
        "audio_bytes": state.audio_bytes,
        "last_audio_at": state.last_audio_at or None,
        "camera_resolution": state.camera_resolution,
        "camera_status": state.camera_status,
        "error": state.error,
    }


def recording_list():
    if not RECORDINGS.exists():
        return []
    files = sorted(RECORDINGS.glob("*.wav"), key=lambda item: item.stat().st_mtime, reverse=True)
    return [
        {
            "name": item.stem,
            "url": "/recordings/" + item.name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.stat().st_mtime)),
            "bytes": item.stat().st_size,
        }
        for item in files
    ]


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/status")
def api_status():
    return status()


@app.post("/api/record/start")
async def record_start():
    if not state.audio_connected:
        raise HTTPException(status_code=503, detail="Microphone device is not connected")
    state.audio_chunks = []
    state.recording = True
    await state.device_audio_socket.send_text("LISTEN_START")
    return status()


@app.post("/api/record/stop")
async def record_stop():
    if state.device_audio_socket is not None:
        await state.device_audio_socket.send_text("LISTEN_STOP")
        await asyncio.sleep(0.5)
    state.recording = False
    if not state.audio_chunks:
        raise HTTPException(status_code=409, detail="No audio samples received")
    RECORDINGS.mkdir(exist_ok=True)
    path = RECORDINGS / time.strftime("recording_%Y%m%d_%H%M%S.wav")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(state.audio_chunks))
    state.last_recording = "/recordings/" + path.name
    state.audio_chunks = []
    return status()


@app.get("/api/recordings")
def recordings():
    return recording_list()


@app.post("/api/sd/test")
async def sd_test():
    if state.device_camera_socket is None:
        raise HTTPException(status_code=503, detail="Camera device is not connected")
    state.sd_status = "SD test command sent"
    socket = state.device_camera_socket
    try:
        await socket.send_text("sd_test")
    except (RuntimeError, WebSocketDisconnect):
        if state.device_camera_socket is socket:
            state.device_camera_socket = None
            state.camera_connected = False
        state.sd_status = "SD test failed: camera device disconnected"
        raise HTTPException(status_code=503, detail=state.sd_status)
    return status()


@app.post("/api/camera/resolution")
async def set_camera_resolution(request: CameraResolutionRequest):
    key = request.resolution.lower()
    if key not in CAMERA_RESOLUTIONS:
        raise HTTPException(status_code=400, detail="Unsupported camera resolution")
    if state.device_camera_socket is None:
        raise HTTPException(status_code=503, detail="Camera device is not connected")
    state.camera_status = "Applying camera resolution"
    await state.device_camera_socket.send_text("camera_size:" + key)
    return status()


@app.get("/recordings/{name}")
def recording(name: str):
    path = RECORDINGS / Path(name).name
    if not path.is_file() or path.suffix.lower() != ".wav":
        raise HTTPException(status_code=404, detail="Recording not found")
    return FileResponse(path, media_type="audio/wav")


@app.websocket("/ws/camera")
async def camera_socket(websocket: WebSocket):
    await websocket.accept()
    state.camera_connected = True
    state.device_camera_socket = websocket
    try:
        while True:
            message = await websocket.receive()
            if message.get("text"):
                device_status = message["text"]
                if device_status.startswith("SD_"):
                    state.sd_status = device_status
                elif device_status.startswith("CAMERA_SIZE_"):
                    state.camera_status = device_status
                    if " size=" in device_status:
                        state.camera_resolution = device_status.split(" size=", 1)[1].split(" ", 1)[0]
                continue
            jpeg = message.get("bytes")
            if jpeg is None:
                continue
            image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                state.error = "Invalid JPEG from device"
                continue
            state.camera_resolution = f"{image.shape[1]}x{image.shape[0]}"
            with frame_lock:
                state.latest_bgr = image
                state.frame_id += 1
                state.last_frame_at = time.time()
            state.error = ""
    except (RuntimeError, WebSocketDisconnect):
        pass
    finally:
        if state.device_camera_socket is websocket:
            state.device_camera_socket = None
            state.camera_connected = False


@app.websocket("/ws/audio")
async def audio_socket(websocket: WebSocket):
    await websocket.accept()
    state.audio_connected = True
    state.device_audio_socket = websocket
    try:
        while True:
            message = await websocket.receive()
            pcm = message.get("bytes")
            if pcm is None:
                continue
            state.audio_packets += 1
            state.audio_bytes += len(pcm)
            state.last_audio_at = time.time()
            if state.recording:
                state.audio_chunks.append(pcm)
    except (RuntimeError, WebSocketDisconnect):
        pass
    finally:
        if state.device_audio_socket is websocket:
            state.device_audio_socket = None
            state.audio_connected = False


@app.get("/api/stream")
def stream():
    def frames():
        last_id = -1
        while True:
            with frame_lock:
                frame_id = state.frame_id
                image = None if state.latest_bgr is None else state.latest_bgr.copy()
            if image is None or frame_id == last_id:
                time.sleep(0.03)
                continue
            last_id = frame_id
            annotated = detect(image)
            ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if ok:
                data = encoded.tobytes()
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")
