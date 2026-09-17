# Arduino bridge

Run the laptop service:

    conda run -n pyg python -m uvicorn app:app --app-dir glass/bridge --host 0.0.0.0 --port 8002

Open `http://127.0.0.1:8002/`. The Arduino firmware connects to the laptop at
`ws://192.168.1.2:8002/ws/camera` and `/ws/audio` by default. This bridge
keeps camera frames local, runs YOLO locally, and records PDM PCM into WAV only
when the page's recording button is active.
