#!/usr/bin/env python
import base64
import json
import os
import struct
import sys

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = None
    filedialog = None


def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) == 0:
        return None
    msg_len = struct.unpack("<I", raw_len)[0]
    data = sys.stdin.buffer.read(msg_len)
    if not data:
        return None
    return json.loads(data.decode("utf-8"))


def send_message(message):
    encoded = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def pick_folder(initial_dir=None):
    if tk is None or filedialog is None:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(initialdir=initial_dir or os.getcwd())
    root.destroy()
    return folder or None


def save_csv(target_dir, filename, base64_data):
    if not target_dir:
        raise ValueError("Missing target_dir")
    os.makedirs(target_dir, exist_ok=True)
    safe_name = os.path.basename(filename)
    path = os.path.join(target_dir, safe_name)
    data = base64.b64decode(base64_data)
    with open(path, "wb") as f:
        f.write(data)
    return path


while True:
    msg = read_message()
    if msg is None:
        break
    try:
        if msg.get("type") == "pickFolder":
            initial = msg.get("initialDir")
            chosen = pick_folder(initial)
            send_message({"ok": True, "folder": chosen})
        elif msg.get("type") == "saveCsv":
            target_dir = msg.get("targetDir")
            filename = msg.get("filename")
            base64_data = msg.get("base64")
            path = save_csv(target_dir, filename, base64_data)
            send_message({"ok": True, "path": path})
        else:
            send_message({"ok": False, "error": "Unknown message type"})
    except Exception as e:
        send_message({"ok": False, "error": str(e)})
