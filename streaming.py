#!/usr/bin/env python3
import errno
import inspect
import platform
import queue
import socket
import threading
import time

import sounddevice as sd


PORT_BASE = 50000
PORT_SPAN = 1000
DEFAULT_PORT = 50007


def detect_os():
    name = platform.system()
    return name or "Unknown"


def _default_devices():
    default_in = None
    default_out = None
    try:
        default_in, default_out = sd.default.device
    except Exception:
        pass
    return default_in, default_out


def _wasapi_loopback_supported():
    if not hasattr(sd, "WasapiSettings"):
        return False
    try:
        params = inspect.signature(sd.WasapiSettings).parameters
        return "loopback" in params
    except Exception:
        try:
            sd.WasapiSettings(loopback=True)
            return True
        except TypeError:
            return False


def get_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return None
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _parse_ipv4(host):
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        ip = host
    parts = ip.split(".")
    if len(parts) != 4:
        raise ValueError("IPv4 address required")
    try:
        octets = [int(part) for part in parts]
    except ValueError as exc:
        raise ValueError("Invalid IPv4 address") from exc
    for value in octets:
        if value < 0 or value > 255:
            raise ValueError("Invalid IPv4 address")
    return octets


def advertised_host(bind_host):
    if not bind_host or bind_host == "0.0.0.0":
        ip = get_lan_ip()
        if ip:
            return ip
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    return bind_host


def encode_pair_code(host, port):
    if port is None:
        port = DEFAULT_PORT
    offset = int(port) - PORT_BASE
    if offset < 0 or offset >= PORT_SPAN:
        raise ValueError("Port out of range for short codes")
    _, _, c, d = _parse_ipv4(host)
    return f"{c:03d}{d:03d}{offset:03d}"


def decode_pair_code(code):
    if not code:
        raise ValueError("Empty code")
    digits = "".join(ch for ch in code if ch.isdigit())
    if len(digits) != 9:
        raise ValueError("Code must be 9 digits")
    c = int(digits[0:3])
    d = int(digits[3:6])
    offset = int(digits[6:9])
    if c > 255 or d > 255:
        raise ValueError("Invalid code")
    local_ip = get_lan_ip()
    if not local_ip:
        raise ValueError("Could not determine local IP")
    a, b, _, _ = _parse_ipv4(local_ip)
    port = PORT_BASE + offset
    host = f"{a}.{b}.{c}.{d}"
    return host, port


def _bind_server_socket(bind_host, port):
    def make_socket():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        return sock

    if port is not None:
        server = make_socket()
        server.bind((bind_host, int(port)))
        server.listen(1)
        return server, int(port)

    candidates = [DEFAULT_PORT]
    for offset in range(PORT_SPAN):
        candidate = PORT_BASE + offset
        if candidate not in candidates:
            candidates.append(candidate)

    last_error = None
    for candidate in candidates:
        server = make_socket()
        try:
            server.bind((bind_host, candidate))
            server.listen(1)
            return server, candidate
        except OSError as exc:
            last_error = exc
            server.close()
            if exc.errno in (errno.EADDRINUSE, errno.EACCES):
                continue
            raise

    if last_error:
        raise last_error
    raise OSError("No free ports available")


def normalize_device(device):
    if device is None:
        return None
    if isinstance(device, str):
        device = device.strip()
        if not device:
            return None
        if device.isdigit():
            return int(device)
    return device


def _find_windows_loopback_device():
    keywords = ("stereo mix", "what u hear", "loopback", "monitor")
    try:
        devices = sd.query_devices()
    except Exception:
        return None
    for idx, dev in enumerate(devices):
        name = str(dev.get("name", "")).lower()
        if int(dev.get("max_input_channels", 0)) > 0:
            if any(word in name for word in keywords):
                return idx
    return None


def _try_wasapi_loopback(log):
    if not _wasapi_loopback_supported():
        return None


def _adjust_input_device(device, channels, log):
    channels = max(1, int(channels))
    info = None
    if device is None:
        default_in, _ = _default_devices()
        device = default_in
    if device is not None:
        try:
            info = sd.query_devices(device)
        except Exception as exc:
            log(f"Device query failed: {exc}")
            info = None
    if info is not None and int(info.get("max_input_channels", 0)) <= 0:
        log("Selected device has no input channels; using default input.")
        default_in, _ = _default_devices()
        device = default_in
        try:
            info = sd.query_devices(device) if device is not None else None
        except Exception:
            info = None
    if info is not None:
        max_ch = int(info.get("max_input_channels", 0))
        if max_ch > 0 and channels > max_ch:
            log(f"Reducing channels to {max_ch} to match device.")
            channels = max_ch
    return device, channels
    try:
        return sd.WasapiSettings(loopback=True)
    except TypeError:
        log(
            "This sounddevice build does not support WASAPI loopback. "
            "Enable 'Stereo Mix' or install a virtual cable and select it."
        )
        return None


def list_devices():
    devices = sd.query_devices()
    inputs = []
    outputs = []
    for idx, dev in enumerate(devices):
        name = dev.get("name", f"Device {idx}")
        max_in = int(dev.get("max_input_channels", 0))
        max_out = int(dev.get("max_output_channels", 0))
        if max_in > 0:
            inputs.append({"index": idx, "name": name, "channels": max_in})
        if max_out > 0:
            outputs.append({"index": idx, "name": name, "channels": max_out})

    default_in, default_out = _default_devices()

    os_name = detect_os()
    if os_name == "Windows":
        loopback_supported = _wasapi_loopback_supported()
        if loopback_supported:
            system_devices = outputs
            default_system = default_out
            system_note = "Windows loopback capture uses the output device."
        else:
            system_devices = inputs
            default_system = default_in
            system_note = (
                "Loopback not supported. Use Stereo Mix or a virtual cable input."
            )
        system_supported = True
    elif os_name == "Darwin":
        system_devices = inputs
        default_system = default_in
        system_note = (
            "macOS needs a virtual input device like BlackHole or Loopback."
        )
        system_supported = True
    elif os_name == "Linux":
        system_devices = inputs
        default_system = default_in
        system_note = "Select a monitor input from PulseAudio/PipeWire."
        system_supported = True
    else:
        system_devices = inputs
        default_system = default_in
        system_note = "System audio may require a virtual input device."
        system_supported = False

    return {
        "os": os_name,
        "inputs": inputs,
        "outputs": outputs,
        "default_input": default_in,
        "default_output": default_out,
        "system_supported": system_supported,
        "system_devices": system_devices,
        "default_system_device": default_system,
        "system_note": system_note,
    }


def client_worker(
    host,
    port,
    samplerate,
    channels,
    blocksize,
    device,
    max_queue,
    stop_event,
    log,
    source="mic",
    state_cb=None,
):
    source = (source or "mic").strip().lower()
    if source not in ("mic", "system"):
        source = "mic"

    device = normalize_device(device)
    os_name = detect_os()
    default_in, default_out = _default_devices()
    extra_settings = None
    if source == "system":
        if os_name == "Windows":
            extra_settings = _try_wasapi_loopback(log)
            if extra_settings is not None:
                if device is None:
                    device = default_out
                log("Using WASAPI loopback for system audio.")
            else:
                if device is None:
                    loopback_device = _find_windows_loopback_device()
                    if loopback_device is not None:
                        device = loopback_device
                        log("Using loopback input device for system audio.")
                    else:
                        log(
                            "No loopback input device found; default input "
                            "will be used (likely microphone)."
                        )
        else:
            if device is None:
                device = default_in
            log(f"System audio on {os_name} needs a virtual input device.")
    if extra_settings is None:
        device, channels = _adjust_input_device(device, channels, log)
    network_channels = max(1, int(channels))
    capture_channels = network_channels
    if extra_settings is not None:
        try:
            info = sd.query_devices(device if device is not None else default_out)
        except Exception:
            info = None
        if info is not None:
            max_out = int(info.get("max_output_channels", 0))
            if max_out > 0:
                capture_channels = max_out
                if network_channels != capture_channels:
                    log(
                        f"Loopback capture uses {capture_channels} channels; "
                        "downmixing to mono."
                    )
                    if network_channels != 1:
                        network_channels = capture_channels
    elif source == "system":
        try:
            info = sd.query_devices(device) if device is not None else None
        except Exception:
            info = None
        if info is not None:
            max_in = int(info.get("max_input_channels", 0))
            if max_in > 0 and max_in != capture_channels:
                capture_channels = max_in
                if network_channels == 1 and capture_channels > 1:
                    log(
                        f"Input device uses {capture_channels} channels; "
                        "downmixing to mono."
                    )
    block_bytes = int(blocksize) * int(network_channels) * 2  # int16
    audio_queue = queue.Queue(maxsize=int(max_queue))

    def set_state(key, value):
        if state_cb is None:
            return
        try:
            state_cb(key, value)
        except Exception:
            pass

    set_state("client_running", True)
    set_state("client_connected", False)

    try:
        sock = socket.create_connection((host, int(port)), timeout=5.0)
        sock.settimeout(None)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError as exc:
        log(f"Connect failed: {exc}")
        set_state("client_error", f"Connect failed: {exc}")
        set_state("client_running", False)
        return
    log(f"Connected to {host}:{port}")
    set_state("client_connected", True)
    set_state("client_error", "")

    def sender():
        try:
            while True:
                data = audio_queue.get()
                if data is None:
                    break
                try:
                    sock.sendall(data)
                except OSError as exc:
                    log(f"Sender stopped: {exc}")
                    stop_event.set()
                    set_state("client_error", f"Send failed: {exc}")
                    set_state("client_connected", False)
                    break
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def callback(indata, frames, time_info, status):
        if stop_event.is_set():
            return
        if status:
            log(f"Input status: {status}")
        if capture_channels != network_channels and network_channels == 1:
            try:
                mono = (indata.astype("int32").sum(axis=1) // capture_channels).astype(
                    "int16"
                )
            except Exception:
                return
            data = mono.tobytes()
        else:
            data = indata.tobytes()
        if len(data) != block_bytes:
            return
        try:
            audio_queue.put_nowait(data)
        except queue.Full:
            pass

    sender_thread = threading.Thread(target=sender, daemon=True)
    sender_thread.start()

    try:
        stream_kwargs = {
            "samplerate": int(samplerate),
            "channels": int(capture_channels),
            "dtype": "int16",
            "blocksize": int(blocksize),
            "device": device,
            "callback": callback,
        }
        if extra_settings is not None:
            stream_kwargs["extra_settings"] = extra_settings

        with sd.InputStream(**stream_kwargs):
            source_label = "system audio" if source == "system" else "microphone"
            log(
                f"Streaming {source_label} to {host}:{port} at "
                f"{samplerate} Hz, {network_channels} ch."
            )
            while not stop_event.is_set():
                time.sleep(0.2)
    except Exception as exc:
        log(f"Client error: {exc}")
        set_state("client_error", f"Client error: {exc}")
        stop_event.set()
    finally:
        while True:
            try:
                audio_queue.put_nowait(None)
                break
            except queue.Full:
                try:
                    audio_queue.get_nowait()
                except queue.Empty:
                    pass
        sender_thread.join(timeout=1.0)
        set_state("client_connected", False)
        set_state("client_running", False)
        log("Client stopped")


def _recv_exact(sock, nbytes, stop_event):
    data = bytearray()
    while len(data) < nbytes:
        if stop_event.is_set():
            return None
        try:
            chunk = sock.recv(nbytes - len(data))
        except socket.timeout:
            continue
        except OSError:
            return None
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


def server_worker(
    bind_host,
    port,
    samplerate,
    channels,
    blocksize,
    device,
    stop_event,
    log,
    state_cb=None,
):
    device = normalize_device(device)
    block_bytes = int(blocksize) * int(channels) * 2  # int16

    def set_state(key, value):
        if state_cb is None:
            return
        try:
            state_cb(key, value)
        except Exception:
            pass

    set_state("server_running", True)
    set_state("server_connected", False)

    try:
        server, bound_port = _bind_server_socket(bind_host, port)
    except OSError as exc:
        log(f"Server bind failed: {exc}")
        set_state("server_error", f"Bind failed: {exc}")
        set_state("server_running", False)
        return

    set_state("server_port", bound_port)
    set_state("server_host", advertised_host(bind_host))
    set_state("server_error", "")
    log(f"Listening on {bind_host}:{bound_port}")

    try:
        while not stop_event.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except OSError as exc:
                log(f"Accept error: {exc}")
                set_state("server_error", f"Accept error: {exc}")
                break

            log(f"Client connected: {addr[0]}:{addr[1]}")
            set_state("server_connected", True)
            conn.settimeout(0.5)
            try:
                with sd.RawOutputStream(
                    samplerate=int(samplerate),
                    channels=int(channels),
                    dtype="int16",
                    blocksize=int(blocksize),
                    device=device,
                ) as stream:
                    while not stop_event.is_set():
                        data = _recv_exact(conn, block_bytes, stop_event)
                        if data is None:
                            break
                        stream.write(data)
            except Exception as exc:
                log(f"Stream error: {exc}")
                set_state("server_error", f"Stream error: {exc}")
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
                set_state("server_connected", False)
                log("Client disconnected")
    finally:
        server.close()
        set_state("server_running", False)
        log("Server stopped")
