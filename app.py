#!/usr/bin/env python3
import threading
import time
from collections import deque

import webview

import streaming

HTML = r"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Sound Transport</title>
    <style>
      :root {
        --bg1: #f3efe5;
        --bg2: #e6f0ff;
        --ink: #232323;
        --muted: #5f6166;
        --accent: #1a5d8f;
        --accent-2: #d77a1c;
        --card: #ffffff;
        --stroke: #d9d3c7;
        --shadow: rgba(0, 0, 0, 0.08);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Trebuchet MS", Verdana, Tahoma, sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at 15% 15%, #fff6d8 0, transparent 55%),
          radial-gradient(circle at 85% 10%, #dff2ff 0, transparent 45%),
          linear-gradient(135deg, var(--bg1), var(--bg2));
        min-height: 100vh;
      }
      .wrap {
        max-width: 980px;
        margin: 24px auto;
        padding: 12px 18px 28px;
      }
      .hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 16px 18px;
        border-radius: 16px;
        background: var(--card);
        box-shadow: 0 12px 30px var(--shadow);
        border: 1px solid var(--stroke);
      }
      .hero h1 {
        margin: 0 0 6px 0;
        font-family: "Palatino Linotype", "Book Antiqua", Palatino, serif;
        font-size: 28px;
        letter-spacing: 0.6px;
      }
      .hero p {
        margin: 0;
        color: var(--muted);
        font-size: 14px;
      }
      .badge {
        padding: 6px 12px;
        border-radius: 999px;
        background: linear-gradient(120deg, var(--accent), var(--accent-2));
        color: #fff;
        font-weight: 600;
        letter-spacing: 0.4px;
        font-size: 12px;
        text-transform: uppercase;
      }
      .mode {
        margin: 16px 0 8px;
        display: inline-flex;
        padding: 6px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid var(--stroke);
        box-shadow: 0 8px 16px var(--shadow);
      }
      .pill {
        border: none;
        background: transparent;
        padding: 8px 16px;
        font-weight: 600;
        color: var(--muted);
        cursor: pointer;
        border-radius: 999px;
      }
      .pill.active {
        background: var(--accent);
        color: #fff;
      }
      .panel {
        display: none;
        margin-top: 16px;
        padding: 18px;
        border-radius: 16px;
        background: var(--card);
        border: 1px solid var(--stroke);
        box-shadow: 0 12px 30px var(--shadow);
        animation: fadeUp 0.45s ease both;
      }
      .panel.active { display: block; }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 14px;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 6px;
        font-size: 13px;
        color: var(--muted);
      }
      .field input, .field select {
        padding: 8px 10px;
        border-radius: 10px;
        border: 1px solid var(--stroke);
        font-size: 14px;
      }
      .actions {
        display: flex;
        gap: 10px;
        margin-top: 14px;
      }
      .btn {
        border: none;
        padding: 10px 16px;
        border-radius: 12px;
        font-weight: 700;
        cursor: pointer;
        background: var(--accent);
        color: #fff;
      }
      .btn.secondary { background: #444; }
      .status {
        margin-top: 10px;
        font-size: 12px;
        color: var(--muted);
      }
      .note {
        margin-top: 8px;
        font-size: 12px;
        color: var(--muted);
      }
      .logwrap {
        margin-top: 18px;
        padding: 12px;
        border-radius: 12px;
        border: 1px dashed var(--stroke);
        background: rgba(255, 255, 255, 0.7);
      }
      .logwrap h3 {
        margin: 0 0 8px;
        font-size: 12px;
        letter-spacing: 1px;
        text-transform: uppercase;
        color: var(--muted);
      }
      pre {
        margin: 0;
        font-size: 12px;
        line-height: 1.35;
        max-height: 140px;
        overflow: auto;
      }
      @keyframes fadeUp {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
      }
      body.ready .hero { animation: fadeUp 0.5s ease both; }
      body.ready .mode { animation: fadeUp 0.6s ease both; }
      body.ready .panel.active { animation: fadeUp 0.7s ease both; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="hero">
        <div>
          <h1>Sound Transport</h1>
          <p>Send microphone or system audio, or receive a stream on this machine.</p>
          <p id="os-note" class="note"></p>
        </div>
        <div class="badge">TCP audio</div>
      </div>

      <div class="mode">
        <button id="mode-send" class="pill">Send</button>
        <button id="mode-recv" class="pill">Receive</button>
      </div>

      <section id="panel-send" class="panel">
        <div class="grid">
          <label class="field">Connection code
            <input
              id="client-code"
              placeholder="123 456 789"
              inputmode="numeric"
              pattern="[0-9 ]*"
              autocomplete="off"
              maxlength="11"
            />
          </label>
          <label class="field">Capture source
            <select id="client-source">
              <option value="mic">Microphone</option>
              <option value="system" selected>System audio</option>
            </select>
          </label>
          <label class="field">Capture device
            <select id="client-device"></select>
          </label>
        </div>
        <div class="actions">
          <button class="btn" id="client-start">Start sending</button>
          <button class="btn secondary" id="client-stop">Stop</button>
        </div>
        <div class="status" id="client-status">Idle</div>
        <div class="note" id="client-code-note">Paste the code from the receiver.</div>
        <div class="note" id="client-source-note"></div>
      </section>

      <section id="panel-recv" class="panel">
        <div class="grid">
          <label class="field">Share code
            <input
              id="server-code"
              readonly
              inputmode="numeric"
              maxlength="11"
            />
          </label>
          <label class="field">Output device
            <select id="server-device"></select>
          </label>
        </div>
        <div class="actions">
          <button class="btn" id="server-start">Start receiving</button>
          <button class="btn secondary" id="server-stop">Stop</button>
        </div>
        <div class="status" id="server-status">Idle</div>
        <div class="note" id="server-code-note">Give this code to the sender.</div>
      </section>

      <div class="logwrap">
        <h3>Activity</h3>
        <pre id="log"></pre>
      </div>
    </div>

    <script>
      const DEFAULT_MODE = "{{DEFAULT_MODE}}";
      const els = (id) => document.getElementById(id);
      const panels = { send: els("panel-send"), recv: els("panel-recv") };
      const pills = { send: els("mode-send"), recv: els("mode-recv") };
      let deviceData = null;

      function digitsOnly(value) {
        return (value || "").replace(/\D/g, "").slice(0, 9);
      }

      function formatCode(value) {
        const digits = digitsOnly(value);
        const groups = [];
        for (let i = 0; i < digits.length; i += 3) {
          groups.push(digits.slice(i, i + 3));
        }
        return groups.join(" ");
      }

      function setMode(mode) {
        Object.keys(panels).forEach((key) => {
          panels[key].classList.toggle("active", key === mode);
          pills[key].classList.toggle("active", key === mode);
        });
      }

      function fillSelect(select, items, defaultIndex) {
        select.innerHTML = "";
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Default";
        select.appendChild(opt);
        items.forEach((item) => {
          const option = document.createElement("option");
          option.value = String(item.index);
          option.textContent = `${item.index}: ${item.name}`;
          if (defaultIndex !== null && Number(defaultIndex) === item.index) {
            option.selected = true;
          }
          select.appendChild(option);
        });
      }

      function applyClientDeviceList() {
        if (!deviceData) {
          return;
        }
        const source = els("client-source").value;
        let devices = deviceData.inputs || [];
        let defaultDevice = deviceData.default_input;
        let note = "";
        if (source === "system") {
          devices = deviceData.system_devices || devices;
          defaultDevice = deviceData.default_system_device;
          note = deviceData.system_note || "";
        }
        fillSelect(els("client-device"), devices, defaultDevice);
        els("client-source-note").textContent = note;
      }

      function applyOsNote() {
        if (!deviceData || !deviceData.os) {
          return;
        }
        els("os-note").textContent = `Detected OS: ${deviceData.os}`;
      }

      async function loadDevices() {
        const api = window.pywebview.api;
        const data = await api.list_devices();
        deviceData = data || {};
        if (els("client-source").value !== "system") {
          els("client-source").value = "system";
        }
        applyClientDeviceList();
        fillSelect(els("server-device"), data.outputs || [], data.default_output);
        applyOsNote();
      }

      async function startClient() {
        const api = window.pywebview.api;
        const cfg = {
          code: digitsOnly(els("client-code").value),
          source: els("client-source").value,
          device: els("client-device").value,
        };
        await api.start_client(cfg);
      }

      async function stopClient() {
        await window.pywebview.api.stop_client();
      }

      async function startServer() {
        const api = window.pywebview.api;
        const cfg = {
          device: els("server-device").value,
        };
        await api.start_server(cfg);
      }

      async function stopServer() {
        await window.pywebview.api.stop_server();
      }

      async function refreshStatus() {
        const api = window.pywebview.api;
        const status = await api.get_status();
        const clientRunning = status.client.running;
        const clientConnected = status.client.connected;
        const serverRunning = status.server.running;
        const serverConnected = status.server.connected;
        const serverCode = status.server.code || "";
        const clientError = status.client.error || "";
        const serverError = status.server.error || "";
        els("client-status").textContent = clientRunning
          ? (clientConnected ? "Sending..." : "Connecting...")
          : (clientError ? `Error: ${clientError}` : "Idle");
        els("server-status").textContent = serverRunning
          ? (serverConnected ? "Connected" : "Waiting for sender")
          : (serverError ? `Error: ${serverError}` : "Idle");
        els("server-code").value = formatCode(serverCode);
        if (!serverCode) {
          els("server-code").setAttribute("placeholder", "Start receiving...");
        } else {
          els("server-code").removeAttribute("placeholder");
        }
        els("client-start").disabled = status.client.running;
        els("client-stop").disabled = !status.client.running;
        els("server-start").disabled = status.server.running;
        els("server-stop").disabled = !status.server.running;
        els("log").textContent = (status.logs || []).join("\n");
      }

      function wireEvents() {
        pills.send.addEventListener("click", () => setMode("send"));
        pills.recv.addEventListener("click", () => setMode("recv"));
        els("client-start").addEventListener("click", startClient);
        els("client-stop").addEventListener("click", stopClient);
        els("client-source").addEventListener("change", applyClientDeviceList);
        els("client-code").addEventListener("input", () => {
          els("client-code").value = formatCode(els("client-code").value);
        });
        els("server-start").addEventListener("click", startServer);
        els("server-stop").addEventListener("click", stopServer);
      }

      function init() {
        setMode(DEFAULT_MODE === "recv" ? "recv" : "send");
        wireEvents();
        loadDevices();
        refreshStatus();
        setInterval(refreshStatus, 800);
        document.body.classList.add("ready");
      }

      window.addEventListener("pywebviewready", init);
    </script>
  </body>
</html>
"""


class StreamController:
    def __init__(self):
        self.client_thread = None
        self.server_thread = None
        self.client_stop = threading.Event()
        self.server_stop = threading.Event()
        self.logs = deque(maxlen=200)
        self.log_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.state = {
            "client_running": False,
            "client_connected": False,
            "server_running": False,
            "server_connected": False,
            "server_port": None,
            "server_host": None,
            "client_error": "",
            "server_error": "",
        }

    def _log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        line = f"{timestamp} {message}"
        with self.log_lock:
            self.logs.append(line)

    def _coerce_int(self, value, default, label):
        try:
            return int(value)
        except (TypeError, ValueError):
            self._log(f"Invalid {label}, using {default}")
            return default

    def _set_state(self, key, value):
        with self.state_lock:
            self.state[key] = value

    def _client_running(self):
        if self.client_thread and self.client_thread.is_alive():
            return True
        self.client_thread = None
        self._set_state("client_running", False)
        self._set_state("client_connected", False)
        return False

    def _server_running(self):
        if self.server_thread and self.server_thread.is_alive():
            return True
        self.server_thread = None
        self._set_state("server_running", False)
        self._set_state("server_connected", False)
        self._set_state("server_port", None)
        self._set_state("server_host", None)
        return False

    def start_client(self, cfg):
        if self._client_running():
            self._log("Client already running")
            return {"ok": False}

        self._set_state("client_error", "")
        code = (cfg.get("code") or "").strip()
        host = (cfg.get("host") or "").strip()
        if code:
            try:
                host, decoded_port = streaming.decode_pair_code(code)
            except ValueError as exc:
                self._log(f"Invalid code: {exc}")
                self._set_state("client_error", "Invalid code")
                return {"ok": False}
            cfg["port"] = decoded_port
            self._log(f"Using code for {host}:{decoded_port}")
        elif not host:
            self._log("Connection code is required")
            self._set_state("client_error", "Connection code is required")
            return {"ok": False}

        port = self._coerce_int(cfg.get("port", 50007), 50007, "client port")
        samplerate = self._coerce_int(cfg.get("samplerate", 44100), 44100, "sample rate")
        channels = self._coerce_int(cfg.get("channels", 1), 1, "channels")
        blocksize = self._coerce_int(cfg.get("blocksize", 1024), 1024, "block size")
        max_queue = self._coerce_int(cfg.get("max_queue", 32), 32, "max queue")
        source = (cfg.get("source") or "mic").strip().lower()

        self.client_stop.clear()
        thread = threading.Thread(
            target=streaming.client_worker,
            args=(
                host,
                port,
                samplerate,
                channels,
                blocksize,
                cfg.get("device"),
                max_queue,
                self.client_stop,
                self._log,
                source,
                self._set_state,
            ),
            daemon=True,
        )
        self.client_thread = thread
        thread.start()
        return {"ok": True}

    def stop_client(self):
        if self._client_running():
            self.client_stop.set()
            return {"ok": True}
        self._log("Client is not running")
        return {"ok": False}

    def start_server(self, cfg):
        if self._server_running():
            self._log("Server already running")
            return {"ok": False}

        self._set_state("server_error", "")
        bind_host = (cfg.get("bind") or "0.0.0.0").strip()
        if not bind_host:
            bind_host = "0.0.0.0"

        port_value = cfg.get("port")
        if port_value is None:
            port = None
        else:
            port = self._coerce_int(port_value, 50007, "server port")
        samplerate = self._coerce_int(cfg.get("samplerate", 44100), 44100, "sample rate")
        channels = self._coerce_int(cfg.get("channels", 1), 1, "channels")
        blocksize = self._coerce_int(cfg.get("blocksize", 1024), 1024, "block size")

        self.server_stop.clear()
        thread = threading.Thread(
            target=streaming.server_worker,
            args=(
                bind_host,
                port,
                samplerate,
                channels,
                blocksize,
                cfg.get("device"),
                self.server_stop,
                self._log,
                self._set_state,
            ),
            daemon=True,
        )
        self.server_thread = thread
        thread.start()
        return {"ok": True}

    def stop_server(self):
        if self._server_running():
            self.server_stop.set()
            return {"ok": True}
        self._log("Server is not running")
        return {"ok": False}

    def status(self):
        client_running = self._client_running()
        server_running = self._server_running()
        with self.log_lock:
            logs = list(self.logs)
        with self.state_lock:
            state = dict(self.state)
        state["client_running"] = client_running
        state["server_running"] = server_running
        if not client_running:
            state["client_connected"] = False
        if not server_running:
            state["server_connected"] = False
            state["server_port"] = None
            state["server_host"] = None
        code = ""
        if server_running and state.get("server_port"):
            host = state.get("server_host") or streaming.advertised_host("0.0.0.0")
            try:
                code = streaming.encode_pair_code(host, state["server_port"])
            except ValueError as exc:
                self._log(f"Code error: {exc}")
        return {
            "client": {
                "running": state["client_running"],
                "connected": state["client_connected"],
                "error": state.get("client_error", ""),
            },
            "server": {
                "running": state["server_running"],
                "connected": state["server_connected"],
                "code": code,
                "error": state.get("server_error", ""),
            },
            "logs": logs,
        }

    def get_pair_code(self, cfg=None):
        cfg = cfg or {}
        with self.state_lock:
            state = dict(self.state)
        if state.get("server_running") and state.get("server_port"):
            host = state.get("server_host") or streaming.advertised_host("0.0.0.0")
            port = state.get("server_port")
            try:
                code = streaming.encode_pair_code(host, port)
            except ValueError as exc:
                self._log(f"Code error: {exc}")
                return {"code": "", "host": host, "port": port}
            return {"code": code, "host": host, "port": port}
        bind_host = (cfg.get("bind") or "0.0.0.0").strip()
        if not bind_host:
            bind_host = "0.0.0.0"
        port = self._coerce_int(cfg.get("port", 50007), 50007, "server port")
        host = streaming.advertised_host(bind_host)
        try:
            code = streaming.encode_pair_code(host, port)
        except ValueError as exc:
            self._log(f"Code error: {exc}")
            return {"code": "", "host": host, "port": port}
        return {"code": code, "host": host, "port": port}


class Api:
    def __init__(self, controller):
        self.controller = controller

    def list_devices(self):
        return streaming.list_devices()

    def start_client(self, cfg):
        return self.controller.start_client(cfg)

    def stop_client(self):
        return self.controller.stop_client()

    def start_server(self, cfg):
        return self.controller.start_server(cfg)

    def stop_server(self):
        return self.controller.stop_server()

    def get_status(self):
        return self.controller.status()

    def get_pair_code(self, cfg=None):
        return self.controller.get_pair_code(cfg)


def run_app(default_mode="send"):
    html = HTML.replace("{{DEFAULT_MODE}}", default_mode or "send")
    controller = StreamController()
    api = Api(controller)
    window = webview.create_window("Sound Transport", html=html, js_api=api)
    webview.start(debug=False, gui=None)


if __name__ == "__main__":
    run_app()
