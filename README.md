# PylaMydd

Brawl Stars automation bot — computer vision + ONNX models, ADB input.

## Requirements

- Python 3.11 / 3.12
- Windows 10/11
- Android device with ADB

## Setup

```bash
pip install -r requirements.txt
pip install "scrcpy-client@git+https://github.com/leng-yue/py-scrcpy-client.git@v0.5.0" --no-deps
pip install "adbutils~=2.12.0"
```

Configure `cfg/` as needed, then:

```bash
set PYTHONPATH=src
set PATH=tools;%PATH%
python -m src.main
```

## Config

| File | Purpose |
|------|---------|
| `cfg/general_config.toml` | IPS limit, session duration, emulator |
| `cfg/bot_config.toml` | Gamemode, detection thresholds |
| `cfg/login.toml` | API key |
| `cfg/time_tresholds.toml` | Check intervals |
