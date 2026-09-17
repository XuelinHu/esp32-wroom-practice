#pragma once

static const char WEB_PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ESP32 Arduino Audio</title>
  <style>
    :root { font-family: Arial, sans-serif; color: #17212b; background: #eef2f5; }
    body { margin: 0; padding: 18px; }
    main { max-width: 760px; margin: auto; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
    h1 { font-size: 22px; margin: 0; }
    section { background: white; border: 1px solid #d4dce3; border-radius: 6px; padding: 14px; margin: 12px 0; }
    .title { font-weight: 700; margin-bottom: 10px; }
    .status { color: #53616e; margin-top: 10px; min-height: 20px; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; }
    button, .upload { border: 0; border-radius: 5px; padding: 9px 13px; color: white; background: #1769aa; cursor: pointer; }
    button.stop { background: #b42318; }
    button.delete { background: #697580; }
    button:disabled { opacity: .5; cursor: wait; }
    input[type=file] { max-width: 100%; }
    .file { border-top: 1px solid #e5e9ed; padding: 12px 0; }
    .file:first-child { border-top: 0; }
    .name { font-weight: 600; overflow-wrap: anywhere; margin-bottom: 8px; }
    .sensor { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .metric { border-left: 3px solid #1769aa; padding-left: 9px; }
    .metric strong { display: block; font-size: 18px; margin-top: 4px; }
    .drive { display: grid; grid-template-columns: repeat(3, 52px); grid-template-rows: repeat(3, 52px); gap: 7px; width: max-content; margin: 0 auto; }
    .drive button { width: 52px; height: 52px; padding: 0; font-size: 24px; touch-action: none; user-select: none; }
    .drive .up { grid-column: 2; }
    .drive .left { grid-column: 1; grid-row: 2; }
    .drive .halt { grid-column: 2; grid-row: 2; background: #b42318; }
    .drive .right { grid-column: 3; grid-row: 2; }
    .drive .down { grid-column: 2; grid-row: 3; }
    .speed { display: grid; grid-template-columns: auto 1fr 42px; align-items: center; gap: 10px; margin: 12px 0; }
    .speed input { width: 100%; }
    #console { margin: 0; max-height: 220px; overflow: auto; white-space: pre-wrap; background: #111820; color: #d8e2ea; padding: 12px; border-radius: 5px; font: 12px/1.5 Consolas, monospace; }
    audio { width: 100%; margin: 6px 0; }
    @media (max-width: 520px) { .sensor { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <header>
    <h1>ESP32 Arduino Audio</h1>
    <button id="refresh">Refresh</button>
  </header>

  <section>
    <div class="title">INMP441 recording</div>
    <div class="actions">
      <button id="recordStart">Start recording</button>
      <button id="recordStop" class="stop">Stop and save</button>
    </div>
    <div id="recordStatus" class="status">Idle</div>
  </section>

  <section>
    <div class="title">4-wheel servo drive</div>
    <div class="drive">
      <button class="up" data-drive="forward" title="Forward" aria-label="Forward">&uarr;</button>
      <button class="left" data-drive="left" title="Left" aria-label="Left">&larr;</button>
      <button class="halt" id="driveStop" title="Stop" aria-label="Stop">&#9632;</button>
      <button class="right" data-drive="right" title="Right" aria-label="Right">&rarr;</button>
      <button class="down" data-drive="backward" title="Backward" aria-label="Backward">&darr;</button>
    </div>
    <label class="speed" for="servoSpeed"><span>Speed</span><input id="servoSpeed" type="range" min="1" max="100" value="45"><output id="servoSpeedValue">45</output></label>
    <div id="servoStatus" class="status">Stopped</div>
  </section>

  <section>
    <div class="title">MAX98357A speaker</div>
    <div class="actions">
      <button id="alphabet">Play A-Z test</button>
      <button id="abc">Start ABC melody</button>
      <button id="playStop" class="stop">Stop playback</button>
    </div>
    <div id="playStatus" class="status">Idle</div>
  </section>

  <section>
    <div class="title">OLED display</div>
    <div class="sensor">
      <div class="metric">24x16 mm / 128x64<strong id="oledPrimary">Unknown</strong></div>
    </div>
    <div class="actions">
      <button data-expression="blink">Blink</button>
      <button data-expression="happy">Happy</button>
      <button data-expression="angry">Angry</button>
      <button data-expression="crying">Crying</button>
      <button data-expression="neutral">Neutral</button>
    </div>
    <div id="oledStatus" class="status">Ready</div>
  </section>

  <section>
    <div class="title">Device console</div>
    <pre id="console">Connecting...</pre>
  </section>

  <section>
    <div class="title">Upload 16-bit mono WAV</div>
    <form id="uploadForm">
      <input id="uploadFile" type="file" name="file" accept="audio/wav,.wav" required>
      <button type="submit">Upload</button>
    </form>
    <div id="uploadStatus" class="status">Use talk/alphabet_announcement.wav for the A-Z test.</div>
  </section>

  <div id="listStatus" class="status">Loading files...</div>
  <section id="files"></section>
</main>
<script>
const $ = selector => document.querySelector(selector);
const recordStart = $('#recordStart');
const recordStop = $('#recordStop');
const playStop = $('#playStop');
let pollTimer = null;
let pollRunning = false;
let driveTimer = null;
let driveDirection = '';

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { cache: 'no-store', ...options });
  } catch (error) {
    throw new Error('Device unavailable. Check ESP32 power and Wi-Fi.');
  }
  const body = await response.text();
  if (!body) throw new Error(`Empty device response (HTTP ${response.status})`);
  let data;
  try {
    data = JSON.parse(body);
  } catch (error) {
    throw new Error(`Invalid device response (HTTP ${response.status})`);
  }
  if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function updateStatus() {
  clearTimeout(pollTimer);
  if (pollRunning) return;
  pollRunning = true;
  try {
    const data = await request('/api/status');
    const logs = await request('/api/logs');
    const recording = data.mode === 'recording';
    const playing = data.mode === 'playing' || data.mode === 'abc';
    recordStart.disabled = data.mode !== 'idle';
    recordStop.disabled = !recording;
    playStop.disabled = !playing;
    $('#recordStatus').textContent = recording
      ? `Recording ${data.bytes} bytes | peak ${data.mic_peak} | ${data.mic_channel}`
      : (data.error ? `Recording error: ${data.error}`
        : (data.last_record ? `${data.last_record} | peak ${data.last_record_peak} | mean ${data.last_record_mean}` : 'Idle'));
    $('#playStatus').textContent = playing ? `${data.mode}: ${data.active_file}` : (data.error || 'Idle');
    $('#oledPrimary').textContent = data.oled_primary_ready ? 'ONLINE' : 'OFFLINE';
    $('#oledStatus').textContent = data.oled_primary_ready ? `Expression: ${data.oled_expression}` : 'Display offline';
    $('#servoStatus').textContent = data.servos_ready
      ? `${data.servo_motion} | speed ${data.servo_speed}`
      : 'Servo PWM unavailable';
    document.querySelectorAll('[data-drive]').forEach(button => { button.disabled = !data.servos_ready; });
    $('#console').textContent = logs.length ? logs.join('\n') : 'No events';
  } catch (error) {
    $('#recordStatus').textContent = error.message;
    $('#playStatus').textContent = error.message;
  } finally {
    pollRunning = false;
    pollTimer = setTimeout(updateStatus, 1500);
  }
}

async function action(path, target) {
  try {
    target.textContent = 'Working...';
    await request(path, { method: 'POST' });
    await updateStatus();
    return true;
  } catch (error) {
    target.textContent = error.message;
    return false;
  }
}

async function sendDrive(direction) {
  const speed = $('#servoSpeed').value;
  try {
    const data = await request(`/api/servo/move?direction=${direction}&speed=${speed}`, { method: 'POST' });
    $('#servoStatus').textContent = `${data.motion} | speed ${data.speed}`;
  } catch (error) {
    $('#servoStatus').textContent = error.message;
    stopDrive(false);
  }
}

function startDrive(direction) {
  if (driveDirection === direction) return;
  stopDrive(false);
  driveDirection = direction;
  sendDrive(direction);
  driveTimer = setInterval(() => sendDrive(direction), 500);
}

function stopDrive(notifyDevice = true) {
  if (driveTimer) clearInterval(driveTimer);
  driveTimer = null;
  const wasDriving = driveDirection !== '';
  driveDirection = '';
  if (notifyDevice && wasDriving) sendDrive('stop');
}

const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

async function waitForRecordingSaved(timeoutMs = 12000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const status = await request('/api/record/status');
    if (status.mode === 'idle') {
      if (status.error) throw new Error(status.error);
      if (!status.last_record) throw new Error('Recording stopped without a saved file.');
      return status;
    }
    await sleep(250);
  }
  throw new Error('Recording finalization timed out.');
}

async function beginRecording() {
  clearTimeout(pollTimer);
  recordStart.disabled = true;
  $('#recordStatus').textContent = 'Starting recording...';
  try {
    await request('/api/record/start', { method: 'POST' });
  } catch (startError) {
    await sleep(400);
    try {
      const status = await request('/api/record/status');
      if (status.mode !== 'recording') throw startError;
    } catch (statusError) {
      $('#recordStatus').textContent = startError.message;
      await updateStatus();
      return;
    }
  }
  await updateStatus();
}

async function loadFiles() {
  const files = $('#files');
  files.replaceChildren();
  try {
    const names = await request('/api/list');
    $('#listStatus').textContent = `${names.length} file(s), newest first`;
    for (const name of names) {
      const row = document.createElement('div');
      row.className = 'file';
      const label = document.createElement('div');
      label.className = 'name';
      label.textContent = name;
      const audio = document.createElement('audio');
      audio.controls = true;
      audio.preload = 'none';
      audio.src = '/recordings/' + encodeURIComponent(name);
      const actions = document.createElement('div');
      actions.className = 'actions';
      const play = document.createElement('button');
      play.textContent = 'Play on ESP32';
      play.onclick = () => action('/api/play/start?name=' + encodeURIComponent(name), $('#playStatus'));
      const remove = document.createElement('button');
      remove.className = 'delete';
      remove.textContent = 'Delete';
      remove.onclick = async () => {
        if (!confirm(`Delete ${name}?`)) return;
        try {
          await request('/api/delete?name=' + encodeURIComponent(name), { method: 'POST' });
          loadFiles();
        } catch (error) { $('#listStatus').textContent = error.message; }
      };
      actions.append(play, remove);
      row.append(label, audio, actions);
      files.append(row);
    }
  } catch (error) {
    $('#listStatus').textContent = error.message;
  }
}

recordStart.onclick = beginRecording;
recordStop.onclick = async () => {
  clearTimeout(pollTimer);
  recordStop.disabled = true;
  $('#recordStatus').textContent = 'Stopping and saving...';
  try {
    await request('/api/record/stop', { method: 'POST' });
    const status = await waitForRecordingSaved();
    $('#recordStatus').textContent = `Saved ${status.last_record}`;
    await loadFiles();
  } catch (error) {
    $('#recordStatus').textContent = error.message;
  } finally {
    await updateStatus();
  }
};
$('#alphabet').onclick = () => action('/api/play/start?name=alphabet_announcement.wav', $('#playStatus'));
$('#abc').onclick = () => action('/api/abc/start', $('#playStatus'));
playStop.onclick = () => action('/api/play/stop', $('#playStatus'));
document.querySelectorAll('[data-expression]').forEach(button => {
  button.onclick = () => action('/api/oled/expression?name=' + button.dataset.expression, $('#oledStatus'));
});
document.querySelectorAll('[data-drive]').forEach(button => {
  button.addEventListener('pointerdown', event => {
    event.preventDefault();
    button.setPointerCapture(event.pointerId);
    startDrive(button.dataset.drive);
  });
  button.addEventListener('pointerup', () => stopDrive());
  button.addEventListener('pointercancel', () => stopDrive());
  button.addEventListener('lostpointercapture', () => stopDrive());
});
$('#driveStop').onclick = () => {
  stopDrive(false);
  sendDrive('stop');
};
$('#servoSpeed').oninput = event => { $('#servoSpeedValue').value = event.target.value; };
window.addEventListener('blur', () => stopDrive());
document.addEventListener('visibilitychange', () => { if (document.hidden) stopDrive(); });
$('#refresh').onclick = loadFiles;
$('#uploadForm').onsubmit = async event => {
  event.preventDefault();
  const file = $('#uploadFile').files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file, file.name);
  try {
    $('#uploadStatus').textContent = 'Uploading...';
    const data = await request('/api/upload', { method: 'POST', body: form });
    $('#uploadStatus').textContent = `Uploaded ${data.name}`;
    loadFiles();
  } catch (error) { $('#uploadStatus').textContent = error.message; }
};

async function initializePage() {
  await updateStatus();
  await loadFiles();
}

initializePage();
</script>
</body>
</html>)HTML";
