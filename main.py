import zipfile
from datetime import datetime, timedelta
import random
import numpy as np
import os
import csv
import json
import time
import shutil
from typing import Optional, Dict, Iterator, List


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
        self.history.append((datetime.now(), self.last_value))
        if self.callback:
            self.callback(self.sensor_id, datetime.now(), self.last_value, self.unit)
        return self.last_value


class HumiditySensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik wilgotności", unit="%", min_value=0, max_value=100, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self, temperature=None):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        temp_factor = 0
        if temperature is not None:
            temp_factor = max(-10, min(10, (25 - temperature) * 0.5))
        humidity = random.uniform(self.min_value, self.max_value) + temp_factor
        humidity = max(self.min_value, min(self.max_value, humidity))
        self.last_value = round(humidity, 2)
        self.history.append((datetime.now(), self.last_value))
        if self.callback:
            self.callback(self.sensor_id, datetime.now(), self.last_value, self.unit)
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
        self.history.append((datetime.now(), self.last_value))
        if self.callback:
            self.callback(self.sensor_id, datetime.now(), self.last_value, self.unit)
        return self.last_value


class Logger:
    def __init__(self, config_path: str):
        with open(config_path, mode='r', newline='', encoding='utf-8') as f:
            self.config = json.load(f)

        self.log_dir = self.config["log_dir"]
        self.filename_pattern = self.config["filename_pattern"]
        self.buffer_size = self.config.get("buffer_size", 100)
        self.rotate_every_hours = self.config.get("rotate_every_hours", 24)
        self.max_size_mb = self.config.get("max_size_mb", 10)
        self.rotate_after_lines = self.config.get("rotate_after_lines", None)
        self.retention_days = self.config.get("retention_days", 30)

        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(os.path.join(self.log_dir, "archive"), exist_ok=True)

        self.buffer: List[List[str]] = []
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

    def log_reading(self, sensor_id: str, timestamp: datetime, value: float, unit: str):
        row = [timestamp.isoformat(), sensor_id, value, unit]
        self.buffer.append(row)

        if len(self.buffer) >= self.buffer_size:
            self._flush()

        if self._needs_rotation():
            self._rotate()

    def _flush(self):
        if not self.current_writer or not self.buffer:
            return
        self.current_writer.writerows(self.buffer)
        self.line_count += len(self.buffer)
        self.buffer.clear()
        self.current_file.flush()

    def _needs_rotation(self) -> bool:
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

    def _archive(self, file_path: str):
        archive_path = f"{file_path}.zip"
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, os.path.basename(file_path))
        os.remove(file_path)

    def delete_old_logs(self):
        retention_threshold = datetime.now() - timedelta(days=self.retention_days)
        archive_dir = os.path.join(self.log_dir, "archive")
        for file_name in os.listdir(archive_dir):
            file_path = os.path.join(archive_dir, file_name)
            if os.path.getmtime(file_path) < retention_threshold.timestamp():
                os.remove(file_path)

    def read_logs(self, start: datetime, end: datetime, sensor_id: Optional[str] = None) -> Iterator[Dict]:
        for file_name in os.listdir(self.log_dir):
            file_path = os.path.join(self.log_dir, file_name)
            if file_path.endswith('.csv'):
                yield from self._parse_csv(file_path, start, end, sensor_id)

        archive_dir = os.path.join(self.log_dir, 'archive')
        for file_name in os.listdir(archive_dir):
            if file_name.endswith('.zip'):
                zip_file_path = os.path.join(archive_dir, file_name)
                yield from self._parse_zip(zip_file_path, start, end, sensor_id)

    def _parse_csv(self, file_path: str, start: datetime, end: datetime, sensor_id: Optional[str]) -> Iterator[Dict]:
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                timestamp = datetime.fromisoformat(row["timestamp"])
                if start <= timestamp <= end:
                    if not sensor_id or row["sensor_id"] == sensor_id:
                        yield row

    def _parse_zip(self, zip_file_path: str, start: datetime, end: datetime, sensor_id: Optional[str]) -> Iterator[Dict]:
        with zipfile.ZipFile(zip_file_path, 'r') as zipf:
            for file_name in zipf.namelist():
                with zipf.open(file_name) as f:
                    f = (line.decode('utf-8') for line in f)
                    reader = csv.DictReader(f)
                    for row in reader:
                        timestamp = datetime.fromisoformat(row["timestamp"])
                        if start <= timestamp <= end:
                            if not sensor_id or row["sensor_id"] == sensor_id:
                                yield row


# Utwórz katalogi
log_dir = 'logs'
archive_dir = os.path.join(log_dir, 'archive')
os.makedirs(log_dir, exist_ok=True)
os.makedirs(archive_dir, exist_ok=True)

# Logger
logger = Logger("config.json")
logger.start()

# Czujniki
temp_sensor = Sensor("T1", "Czujnik temperatury", "°C", -20, 50, frequency=2)
humidity_sensor = Sensor("H1", "Czujnik wilgotności", "%", 0, 100, frequency=2)
pressure_sensor = Sensor("P1", "Czujnik ciśnienia", "hPa", 950, 1050, frequency=2)

temp_sensor.register_callback(logger.log_reading)
humidity_sensor.register_callback(logger.log_reading)
pressure_sensor.register_callback(logger.log_reading)

# Odczyty
for _ in range(10):
    temp_sensor.read_value()
    humidity_sensor.read_value()
    pressure_sensor.read_value()
    time.sleep(2)

logger.stop()

# Sprawdzenie i odczyt archiwów
archived_files = os.listdir(archive_dir)
print(f"Pliki archiwalne: {archived_files}")


if not archived_files:
    print("Brak plików archiwalnych ZIP. Pomijam odczyt archiwów.")
else:
    start_time = datetime.now() - timedelta(minutes=5)
    end_time = datetime.now()

    for file_name in archived_files:
        file_path = os.path.join(archive_dir, file_name)
        if file_path.endswith('.zip'):
            print(f"Odczytuję plik: {file_name}")
            logs = list(logger.read_logs(start_time, end_time))
            print(f"Liczba wpisów w logach: {len(logs)}")
            if not logs:
                print(f"Brak logów w pliku {file_name}")

# Usuwanie starych logów
logger.delete_old_logs()

archived_files_after_deletion = os.listdir(archive_dir)
print(f"Pliki archiwalne po usunięciu: {archived_files_after_deletion}")
