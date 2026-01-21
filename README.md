# Sound Transport

Stream audio from one computer to another over a local network with a simple GUI.

## What It Does
- Send microphone or system audio from a sender
- Receive and play audio on another machine
- Uses a short 9-digit connection code (LAN only)

## Requirements
- Python 3.10+ (3.12 recommended)
- Packages: `pywebview`, `sounddevice`

Install:
```bash
python -m pip install pywebview sounddevice
```

## Run
```bash
python app.py
```

### Send
1) Open the app on the receiving machine and click **Start receiving**.  
2) Copy the 9-digit code.
3) On the sending machine, paste the code and click **Start sending**.
4) Pick **System audio** or **Microphone**, then choose a device if needed.

### Receive
1) Click **Start receiving**.
2) Share the 9-digit code.
3) Watch the status change to **Connected** when the sender joins.

## Notes
- The 9-digit code is for **LAN only** (same local network).
- If the sender is on a different network, you’ll need a longer code or a relay.
- Default audio settings are fixed internally for simplicity.

## System Audio Capture
- **Windows**: Uses WASAPI loopback if available. Otherwise, select **Stereo Mix** or a virtual cable input (VB‑Cable).
- **macOS**: Requires a virtual input device (e.g., BlackHole/Loopback).
- **Linux**: Use a monitor input from PulseAudio/PipeWire.

## Build (Nuitka)
Builds a macOS `.app` or Windows `.exe` depending on the OS you run this on.

```bash
python -m pip install nuitka
python build_nuitka.py --clean
```

## Troubleshooting
- **“Address already in use”**: Another app is using the default port. The receiver auto-picks a free port now; restart both apps if needed.
- **“Invalid code”**: The code must be exactly 9 digits. Make sure both devices are on the same LAN.
- **No UI on Windows**: Install the WebView2 runtime.
