import zipfile
from datetime import datetime, timedelta
import random
from typing import Optional, Dict, Iterator, List
import numpy as np
import os
import csv
import json
import time
import shutil

from network.client import NetworkClient
from server.server import NetworkServer

class Sensor:
    def __init__(self, sensor_id, name, unit, min_value, max_value, frequency=1):
        self.sensor_id = sensor_id
        self.name = name
        self.unit = unit
        self.min_value = min_value
        self.max_value = max_value
        self.frequency = frequency
        self.active = True
        self.last_value = None
        self.history = []
        self.last_read_time = datetime.now()
        self.callback = None

    def register_callback(self, callback_function):
        self.callback = callback_function

    def read_value(self):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        now = datetime.now()
        if (now - self.last_read_time).total_seconds() >= self.frequency:
            value = random.uniform(self.min_value, self.max_value)
            self.last_value = value
            self.history.append((now, value))
            self.last_read_time = now
            if self.callback:
                self.callback(self.sensor_id, now, self.last_value, self.unit)
            return self.last_value

    def calibrate(self, calibration_factor):
        if self.last_value is None:
            self.read_value()
        self.last_value *= calibration_factor
        return self.last_value

    def get_last_value(self):
        if self.last_value is None:
            return self.read_value()
        return self.last_value

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def get_history(self):
        return self.history

    def __str__(self):
        return f"Sensor(id={self.sensor_id}, name={self.name}, unit={self.unit})"


class TemperatureSensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik temperatury", unit="C", min_value=-20, max_value=50, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        value = np.random.uniform(self.min_value, self.max_value)
        self.last_value = round(value, 2)
        now = datetime.now()
        self.history.append((now, self.last_value))
        if self.callback:
            self.callback(self.sensor_id, now, self.last_value, self.unit)
        return self.last_value


class HumiditySensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik wilgotności", unit="%", min_value=0, max_value=100, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self, temperature=None):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        temp_factor = max(-10, min(10, (25 - temperature) * 0.5)) if temperature is not None else 0
        humidity = random.uniform(self.min_value, self.max_value) + temp_factor
        humidity = max(self.min_value, min(self.max_value, humidity))
        self.last_value = round(humidity, 2)
        now = datetime.now()
        self.history.append((now, self.last_value))
        if self.callback:
            self.callback(self.sensor_id, now, self.last_value, self.unit)
        return self.last_value


class PressureSensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik ciśnienia", unit="hPa", min_value=950, max_value=1050, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        pressure = random.gauss((self.min_value + self.max_value) / 2, 5)
        pressure = max(self.min_value, min(self.max_value, pressure))
        self.last_value = round(pressure, 2)
        now = datetime.now()
        self.history.append((now, self.last_value))
        if self.callback:
            self.callback(self.sensor_id, now, self.last_value, self.unit)
        return self.last_value

class LightSensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik światła", unit="lux", min_value=0, max_value=10000, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self):
        # Symulacja natężenia światła:
        # Generuje losową wartość w zakresie (0–10,000 lux), uwzględniając porę dnia.
        # Wartość jest większa w godzinach dziennych (6:00–18:00) i mniejsza w nocy.
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        hour = datetime.now().hour
        light_factor = (10000 if 6 <= hour <= 18 else 0)  # Symulacja zmiany oświetlenia wg pory dnia
        light = random.uniform(self.min_value, self.max_value) * (light_factor / 10000)
        self.last_value = round(light, 2)
        self.history.append((datetime.now(), self.last_value))
        return self.last_value

class Logger:
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.log_dir = self.config["log_dir"]
        self.filename_pattern = self.config["filename_pattern"]
        self.buffer_size = self.config.get("buffer_size", 100)
        self.rotate_every_hours = self.config.get("rotate_every_hours", 24)
        self.max_size_mb = self.config.get("max_size_mb", 10)
        self.rotate_after_lines = self.config.get("rotate_after_lines")
        self.retention_days = self.config.get("retention_days", 30)

        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(os.path.join(self.log_dir, "archive"), exist_ok=True)

        self.buffer = []
        self.current_file = None
        self.current_writer = None
        self.current_file_path = ""
        self.last_rotation_time = datetime.now()
        self.line_count = 0

    def start(self):
        now = datetime.now()
        filename = now.strftime(self.filename_pattern)
        self.current_file_path = os.path.join(self.log_dir, filename)
        file_exists = os.path.exists(self.current_file_path)
        self.current_file = open(self.current_file_path, 'a', newline='', encoding='utf-8')
        self.current_writer = csv.writer(self.current_file)
        if not file_exists:
            self.current_writer.writerow(["timestamp", "sensor_id", "value", "unit"])
        self.last_rotation_time = now
        self.line_count = sum(1 for _ in open(self.current_file_path)) - 1

    def stop(self):
        self._flush()
        if self.current_file:
            self.current_file.close()
            self.current_file = None

    def log_reading(self, sensor_id, timestamp, value, unit):
        row = [timestamp.isoformat(), sensor_id, value, unit]
        self.buffer.append(row)
        if len(self.buffer) >= self.buffer_size:
            self._flush()
        if self._needs_rotation():
            self._rotate()

    def _flush(self):
        if self.current_writer and self.buffer:
            self.current_writer.writerows(self.buffer)
            self.line_count += len(self.buffer)
            self.buffer.clear()
            self.current_file.flush()

    def _needs_rotation(self):
        if datetime.now() - self.last_rotation_time >= timedelta(hours=self.rotate_every_hours):
            return True
        if os.path.exists(self.current_file_path):
            size_mb = os.path.getsize(self.current_file_path) / (1024 * 1024)
            if size_mb >= self.max_size_mb:
                return True
        if self.rotate_after_lines and self.line_count >= self.rotate_after_lines:
            return True
        return False

    def _rotate(self):
        self.stop()
        archived_filename = f"{self.current_file_path}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
        shutil.move(self.current_file_path, archived_filename)
        self._archive(archived_filename)
        self.start()

    def _archive(self, file_path):
        archive_path = f"{file_path}.zip"
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, os.path.basename(file_path))
        os.remove(file_path)

    def delete_old_logs(self):
        threshold = datetime.now() - timedelta(days=self.retention_days)
        archive_dir = os.path.join(self.log_dir, "archive")
        for name in os.listdir(archive_dir):
            path = os.path.join(archive_dir, name)
            if os.path.getmtime(path) < threshold.timestamp():
                os.remove(path)

    def read_logs(self, start, end, sensor_id=None):
        for name in os.listdir(self.log_dir):
            if name.endswith(".csv"):
                yield from self._parse_csv(os.path.join(self.log_dir, name), start, end, sensor_id)
        for name in os.listdir(os.path.join(self.log_dir, "archive")):
            if name.endswith(".zip"):
                yield from self._parse_zip(os.path.join(self.log_dir, "archive", name), start, end, sensor_id)

    def _parse_csv(self, path, start, end, sensor_id):
        with open(path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["timestamp"])
                if start <= ts <= end and (not sensor_id or row["sensor_id"] == sensor_id):
                    yield row

    def _parse_zip(self, zip_path, start, end, sensor_id):
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            for name in zipf.namelist():
                with zipf.open(name) as f:
                    reader = csv.DictReader((line.decode('utf-8') for line in f))
                    for row in reader:
                        ts = datetime.fromisoformat(row["timestamp"])
                        if start <= ts <= end and (not sensor_id or row["sensor_id"] == sensor_id):
                            yield row



# Upewniamy się, że wszystkie katalogi istnieją
log_dir = 'logs'
archive_dir = os.path.join(log_dir, 'archive')
os.makedirs(log_dir, exist_ok=True)
os.makedirs(archive_dir, exist_ok=True)

## Inicjalizacja loggera
logger = Logger("config.json")
logger.start()

# Inicjalizacja czujników
temp_sensor = Sensor("T1", "Czujnik temperatury", "°C", -20, 50, frequency=2)
humidity_sensor = Sensor("H1", "Czujnik wilgotności", "%", 0, 100, frequency=2)
pressure_sensor = Sensor("P1", "Czujnik ciśnienia", "hPa", 950, 1050, frequency=2)
light_sensor = Sensor("L1","Czujnik natężenia światła","lux",0,1000,frequency=2)
# Wybór trybu: klient lub serwer
is_server = logger.config.get("is_server", False)

if is_server:
    print("[INFO] Uruchamianie jako SERWER")
    server = NetworkServer(port=5000)
    server.start()

    # Rejestracja callbacków do logowania lokalnego
    temp_sensor.register_callback(logger.log_reading)
    humidity_sensor.register_callback(logger.log_reading)
    pressure_sensor.register_callback(logger.log_reading)
    light_sensor.register_callback(logger.log_reading)

    try:
        while True:
            temp_sensor.read_value()
            humidity_sensor.read_value()
            pressure_sensor.read_value()
            light_sensor.read_value()
            time.sleep(2)
    except KeyboardInterrupt:
        print("Zatrzymano serwer.")

else:
    print("[INFO] Uruchamianie jako KLIENT")
    client = NetworkClient()

    try:
        client.connect()
    except ConnectionError as e:
        print(f"[ERROR] Nie udało się połączyć z serwerem: {e}")
        logger.stop()
        exit(1)

    # Callback logujący i wysyłający do serwera
    def send_and_log(sensor_id, timestamp, value, unit):
        logger.log_reading(sensor_id, timestamp, value, unit)
        client.send({
            "sensor_id": sensor_id,
            "timestamp": timestamp.isoformat(),
            "value": value,
            "unit": unit
        })

    # Rejestracja callbacków do logowania i wysyłania
    temp_sensor.register_callback(send_and_log)
    humidity_sensor.register_callback(send_and_log)
    pressure_sensor.register_callback(send_and_log)
    light_sensor.register_callback(send_and_log)

    try:
        while True:
            temp_sensor.read_value()
            humidity_sensor.read_value()
            pressure_sensor.read_value()
            light_sensor.read_value()
            time.sleep(2)
    except KeyboardInterrupt:
        print("Zatrzymano klienta.")

# Zakończenie logowania, rotacja pliku
logger.stop()

# Po zakończeniu procesu powinny być już pliki ZIP w katalogu 'archive'
archived_files = os.listdir(archive_dir)
print(f"Pliki archiwalne: {archived_files}")

# Sprawdzenie, czy pliki ZIP zostały utworzone w katalogu 'archive'
assert len(archived_files) > 0, "Nie znaleziono plików archiwalnych ZIP!"

# Przykład: Odczyt logów z archiwalnych plików ZIP
start_time = datetime.now() - timedelta(minutes=5)
end_time = datetime.now()

for file_name in archived_files:
    file_path = os.path.join(archive_dir, file_name)
    if file_path.endswith('.zip'):
        print(f"Odczytuję plik: {file_name}")
        # Odczyt logów z ZIP
        logs = list(logger.read_logs(start_time, end_time))
        print(f"Liczba wpisów w logach: {len(logs)}")
        assert len(logs) > 0, f"Brak logów w pliku {file_name}"

# Usuwanie starych logów (starszych niż 30 dni)
logger.delete_old_logs()

# Potwierdzenie, że archiwalne pliki zostały usunięte
archived_files_after_deletion = os.listdir(archive_dir)
print(f"Pliki archiwalne po usunięciu: {archived_files_after_deletion}")
