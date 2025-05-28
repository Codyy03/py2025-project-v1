import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import queue
import yaml
import os
from datetime import datetime, timedelta

# === Konfiguracja ===
CONFIG_FILE = 'config.yaml'
DEFAULT_PORT = 9999

# === Serwer TCP (mock) ===
import socket
import json


class SensorServer(threading.Thread):
    def __init__(self, port, data_callback, error_callback):
        super().__init__(daemon=True)
        self.port = port
        self.data_callback = data_callback
        self.error_callback = error_callback
        self.running = False
        self.sock = None

    def run(self):
        try:
            self.running = True
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind(('0.0.0.0', self.port))
            self.sock.listen(5)
            self.sock.settimeout(1.0)
            while self.running:
                try:
                    conn, addr = self.sock.accept()
                    with conn:
                        data = conn.recv(1024)
                        if not data:
                            continue
                        try:
                            msg = json.loads(data.decode())
                            self.data_callback(msg)
                        except Exception as e:
                            self.error_callback(f"Błąd dekodowania JSON: {e}")
                except socket.timeout:
                    continue
        except Exception as e:
            self.error_callback(str(e))
        finally:
            if self.sock:
                self.sock.close()

    def stop(self):
        self.running = False


# === Bufor danych i obliczanie średnich ===
class SensorDataBuffer:
    def __init__(self):
        self.data = {}  # sensor_id: [(timestamp, value)]

    def add_reading(self, sensor_id, value, unit):
        now = datetime.now()
        self.data.setdefault(sensor_id, []).append((now, value, unit))
        self.cleanup_old(sensor_id)

    def cleanup_old(self, sensor_id):
        now = datetime.now()
        self.data[sensor_id] = [(ts, val, unit) for ts, val, unit in self.data[sensor_id] if
                                ts > now - timedelta(hours=12)]

    def get_latest(self, sensor_id):
        if sensor_id in self.data and self.data[sensor_id]:
            return self.data[sensor_id][-1]
        return None, None, None

    def get_avg(self, sensor_id, hours):
        now = datetime.now()
        values = [val for ts, val, unit in self.data.get(sensor_id, []) if ts > now - timedelta(hours=hours)]
        if values:
            return sum(values) / len(values)
        return None


# === GUI ===
class SensorServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sensor TCP Server")

        self.server = None
        self.buffer = SensorDataBuffer()

        self.queue = queue.Queue()

        self.build_ui()
        self.load_config()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(2000, self.update_table)

    def build_ui(self):
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(top_frame, text="Port:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_entry = ttk.Entry(top_frame, textvariable=self.port_var, width=8)
        self.port_entry.pack(side="left", padx=5)

        self.start_btn = ttk.Button(top_frame, text="Start", command=self.start_server)
        self.start_btn.pack(side="left", padx=5)
        self.stop_btn = ttk.Button(top_frame, text="Stop", command=self.stop_server, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        self.tree = ttk.Treeview(self.root, columns=("val", "unit", "ts", "avg1h", "avg12h"), show="headings")
        self.tree.heading("val", text="Ostatnia wartość")
        self.tree.heading("unit", text="Jednostka")
        self.tree.heading("ts", text="Timestamp")
        self.tree.heading("avg1h", text="Średnia 1h")
        self.tree.heading("avg12h", text="Średnia 12h")
        self.tree.column("val", width=100)
        self.tree.column("unit", width=80)
        self.tree.column("ts", width=150)
        self.tree.column("avg1h", width=100)
        self.tree.column("avg12h", width=100)
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        self.status_var = tk.StringVar(value="Status: zatrzymany")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        self.status_label.pack(fill="x", side="bottom")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                cfg = yaml.safe_load(f)
                self.port_var.set(cfg.get("port", DEFAULT_PORT))
        else:
            self.port_var.set(str(DEFAULT_PORT))

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump({"port": int(self.port_var.get())}, f)

    def start_server(self):
        try:
            port = int(self.port_var.get())
            self.server = SensorServer(port, self.handle_data, self.handle_error)
            self.server.start()
            self.status_var.set(f"Status: nasłuchiwanie na porcie {port}")
            self.start_btn["state"] = "disabled"
            self.stop_btn["state"] = "normal"
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można uruchomić serwera: {e}")
            self.status_var.set("Status: błąd")

    def stop_server(self):
        if self.server:
            self.server.stop()
            self.server = None
            self.status_var.set("Status: zatrzymany")
            self.start_btn["state"] = "normal"
            self.stop_btn["state"] = "disabled"

    def handle_data(self, msg):
        try:
            # Zmiana z "sensor_id" na "sensor" aby pasowało do oczekiwanego formatu
            sensor = msg.get("sensor") or msg.get("sensor_id")  # Akceptuj oba formaty
            value = float(msg["value"])
            unit = msg["unit"]
            self.buffer.add_reading(sensor, value, unit)
            self.queue.put(sensor)
        except Exception as e:
            self.handle_error(f"Niepoprawne dane: {e}")

    def handle_error(self, err):
        self.status_var.set(f"Status: błąd - {err}")

    def update_table(self):
        updated = set()
        while not self.queue.empty():
            updated.add(self.queue.get())

        for sensor in updated:
            latest = self.buffer.get_latest(sensor)
            avg1h = self.buffer.get_avg(sensor, 1)
            avg12h = self.buffer.get_avg(sensor, 12)
            values = (f"{latest[1]:.2f}" if latest[1] else "",
                      latest[2] or "",
                      latest[0].strftime('%Y-%m-%d %H:%M:%S') if latest[0] else "",
                      f"{avg1h:.2f}" if avg1h else "",
                      f"{avg12h:.2f}" if avg12h else "")

            if sensor in self.tree.get_children():
                self.tree.item(sensor, values=values)
            else:
                self.tree.insert("", "end", iid=sensor, text=sensor, values=values)

        self.root.after(2000, self.update_table)

    def on_close(self):
        self.save_config()
        self.stop_server()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = SensorServerGUI(root)
    root.mainloop()
