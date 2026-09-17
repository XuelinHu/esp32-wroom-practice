# Arduino HTTP API

Default URL after WiFi connects:

```text
http://<ESP32-IP>/
```

All JSON endpoints return `Content-Type: application/json` and disable HTTP caching.
Only one audio operation can run at a time. Starting a second recording, WAV playback,
or ABC playback returns HTTP `409`.

## Unified status

### `GET /api/status`

Example response:

```json
{
  "ok": true,
  "mode": "idle",
  "active": false,
  "bytes": 0,
  "active_file": "",
  "path": "",
  "last_record": "record_20260807_120000.wav",
  "error": "",
  "oled_primary_ready": true,
  "oled_expression": "happy",
  "mic_peak": 0,
  "mic_channel": "left",
  "last_record_peak": 12000,
  "last_record_mean": 900,
  "servos_ready": true,
  "servo_motion": "stopped",
  "servo_speed": 45
}
```

`mode` is one of `idle`, `recording`, `playing`, or `abc`.

## Four-wheel servo drive

| Method | Path | Description |
|---|---|---|
| POST | `/api/servo/move?direction=<direction>&speed=<1-100>` | Move or stop all four servos |
| GET | `/api/servo/status` | Return the unified status object |

`direction` is `forward`, `backward`, `left`, `right`, or `stop`. A movement
command expires after 1.2 seconds, so a controller must refresh it while movement
is intended. The embedded page refreshes every 500 ms while a direction button is held.

## Recording

| Method | Path | Description |
|---|---|---|
| POST | `/api/record/start` | Start INMP441 recording |
| POST | `/api/record/stop` | Request stop; returns HTTP 202 while the WAV is finalized |
| GET | `/api/record/status` | Return the unified status object |

Recordings use 16 kHz, PCM16, mono WAV format. The maximum configured recording
time is 45 seconds, but recording stops earlier when LittleFS is nearly full.
Starting a recording first deletes existing files named `record_*.wav`, so the
device keeps at most one microphone recording. Manually uploaded WAV files are preserved.
After requesting stop, poll `/api/record/status` until `mode` becomes `idle`.
The file is valid only when `error` is empty and `last_record` contains its name.

## Playback

| Method | Path | Description |
|---|---|---|
| POST | `/api/play/start?name=<file.wav>` | Play a WAV through MAX98357A |
| POST | `/api/play/stop` | Stop WAV or ABC playback |
| GET | `/api/play/status` | Return the unified status object |
| POST | `/api/abc/start` | Start looping ABC melody |
| POST | `/api/abc/stop` | Stop ABC melody |
| GET | `/api/abc/status` | Return the unified status object |

The legacy route `POST /api/play/start/<file.wav>` is also supported.
WAV playback supports standard 44-byte PCM WAV headers, 16-bit mono/stereo,
and sample rates from 8 kHz through 48 kHz.

## Files

| Method | Path | Description |
|---|---|---|
| GET | `/api/list` | Return WAV filenames, newest filename first |
| GET | `/recordings/<file.wav>` | Stream/download a WAV file |
| POST | `/api/delete?name=<file.wav>` | Delete one WAV file |
| POST | `/api/upload` | Multipart upload; form field name is `file` |

Upload example:

```powershell
curl.exe -F "file=@talk\alphabet_announcement.wav" http://192.168.1.10/api/upload
```

## OLED display

| Method | Path | Description |
|---|---|---|
| POST | `/api/oled/test` | Run the blink animation |
| POST | `/api/oled/expression?name=<name>` | Show `blink`, `happy`, `angry`, `crying`, or `neutral` |
| GET | `/api/displays/status` | Report display availability |

The 24x16 mm display uses GPIO22 for SDA and GPIO21 for SCL/SCK. Firmware probes
both common SSD1306 addresses, `0x3C` and `0x3D`.

## Device console

| Method | Path | Description |
|---|---|---|
| GET | `/api/logs` | Last 16 device events shown in the HTML console |

## Error format

```json
{"ok":false,"error":"file_not_found"}
```
