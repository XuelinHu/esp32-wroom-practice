# Glass local vision engine

This is the laptop-side local YOLO service. It reads RGB565 frames from the
existing XIAO endpoint and does not send frames to a cloud service.

Run it from the repository root:

    conda run -n pyg python -m uvicorn app:app --app-dir glass/engine --host 0.0.0.0 --port 8001

Open `http://127.0.0.1:8001/`, enter the XIAO IP shown by the serial console,
then select the same 160x120 or 320x240 frame size as the device web page.

The first inference loads `yolo11n.pt`. Ultralytics downloads this lightweight
weight file automatically when it is not already available. Later runs use the
local cached copy.

For initial testing use 160x120. The XIAO currently sends RGB565 raw frames
over Wi-Fi and should use a strong 2.4 GHz signal.
