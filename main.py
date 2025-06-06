import threading
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
from GUI import SensorServerGUI  # Import SensorServerGUI
import tkinter as tk

from network.client import NetworkClient
from server.server import NetworkServer


# === Klasa do zarządzania symulowanym czasem ===
class SimulatedTime:
    """
    Klasa do zarządzania symulowanym czasem.
    1 realna sekunda = 15 symulowanych minut (30 min / 2 sekundy = 15 min/s)
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SimulatedTime, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Ustawienie początkowego czasu na dzisiaj o północy
        self._current_simulated_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.real_seconds_per_simulated_minute = 2 / 30.0  # 2 sekundy realne = 30 minut symulowanych

    @property
    def current_time(self) -> datetime:
        """Zwraca aktualny symulowany czas."""
        return self._current_simulated_time

    def advance_time(self, real_seconds: float):
        """
        Przesuwa symulowany czas do przodu na podstawie upływu rzeczywistego czasu.
        """
        simulated_minutes_passed = real_seconds / self.real_seconds_per_simulated_minute
        self._current_simulated_time += timedelta(minutes=simulated_minutes_passed)
        # print(f"[SimulatedTime] Czas symulowany: {self._current_simulated_time}") # Opcjonalne logowanie


# === Klasy Sensorów ===
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
        self.last_read_time = SimulatedTime().current_time  # Użyj symulowanego czasu
        self.callback = None

    def register_callback(self, callback_function):
        self.callback = callback_function

    def read_value(self):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")

        sim_time = SimulatedTime().current_time  # Pobierz aktualny symulowany czas

        # Sprawdź, czy minął wystarczający czas od ostatniego odczytu w symulowanym czasie
        if (sim_time - self.last_read_time).total_seconds() >= self.frequency:
            value = random.uniform(self.min_value, self.max_value)
            self.last_value = value
            self.history.append((sim_time, value))  # Zapisz symulowany czas
            self.last_read_time = sim_time  # Zaktualizuj ostatni czas odczytu symulowanym czasem
            if self.callback:
                # Wywołaj callback z danymi odczytu (w tym symulowanym czasem)
                self.callback(self.sensor_id, sim_time, self.last_value, self.unit)
            return self.last_value
        return self.last_value  # Zwróć ostatnią wartość, jeśli nie minął czas


class TemperatureSensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik temperatury", unit="C", min_value=-20, max_value=50, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        value = np.random.uniform(self.min_value, self.max_value)
        self.last_value = round(value, 2)
        sim_time = SimulatedTime().current_time
        self.history.append((sim_time, self.last_value))
        if self.callback:
            self.callback(self.sensor_id, sim_time, self.last_value, self.unit)
        return self.last_value


class HumiditySensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik wilgotności", unit="%", min_value=0, max_value=100, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self, temperature=None):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        humidity = random.uniform(self.min_value, self.max_value)
        humidity = max(self.min_value, min(self.max_value, humidity))
        self.last_value = round(humidity, 2)
        sim_time = SimulatedTime().current_time
        self.history.append((sim_time, self.last_value))
        if self.callback:
            self.callback(self.sensor_id, sim_time, self.last_value, self.unit)
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
        sim_time = SimulatedTime().current_time
        self.history.append((sim_time, self.last_value))
        if self.callback:
            self.callback(self.sensor_id, sim_time, self.last_value, self.unit)
        return self.last_value


class LightSensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik światła", unit="lux", min_value=0, max_value=10000, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self):
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        light_factor = 1.0
        light = random.uniform(self.min_value, self.max_value) * light_factor
        self.last_value = round(light, 2)
        sim_time = SimulatedTime().current_time
        self.history.append((sim_time, self.last_value))
        if self.callback:
            self.callback(self.sensor_id, sim_time, self.last_value, self.unit)
        return self.last_value


# === Klasa Loggera ===
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
        try:
            with open(self.current_file_path, 'r', encoding='utf-8') as f:
                self.line_count = sum(1 for _ in f) - 1
                if self.line_count < 0: self.line_count = 0
        except FileNotFoundError:
            self.line_count = 0

    def stop(self):
        self._flush()
        if self.current_file:
            self.current_file.close()
            self.current_file = None

    def log_reading(self, sensor_id, timestamp, value, unit):
        # timestamp to teraz symulowany czas
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
            print(f"[LOGGER] Bufor opróżniony do pliku: {self.current_file_path}, dodano {len(self.buffer)} wpisów.")
            self.buffer.clear()
            self.current_file.flush()

    def _needs_rotation(self):
        if datetime.now() - self.last_rotation_time >= timedelta(hours=self.rotate_every_hours):
            print(f"Rotacja: Czas minął. ({datetime.now() - self.last_rotation_time})")
            return True
        if os.path.exists(self.current_file_path):
            size_mb = os.path.getsize(self.current_file_path) / (1024 * 1024)
            if size_mb >= self.max_size_mb:
                print(f"Rotacja: Rozmiar przekroczony. ({size_mb} MB >= {self.max_size_mb} MB)")
                return True
        if self.rotate_after_lines and self.line_count >= self.rotate_after_lines:
            print(f"Rotacja: Liczba linii przekroczona. ({self.line_count} >= {self.rotate_after_lines})")
            return True
        return False

    def _rotate(self):
        print(f"Rozpoczynam rotację pliku: {self.current_file_path}")
        self.stop()

        if os.path.exists(self.current_file_path):
            archived_filename_base = os.path.basename(self.current_file_path)
            timestamp_suffix = datetime.now().strftime('_%Y%m%d%H%M%S')
            archived_filename_with_ts = f"{archived_filename_base.replace('.csv', '')}{timestamp_suffix}.csv"

            archive_full_path = os.path.join(self.log_dir, "archive", archived_filename_with_ts)

            try:
                shutil.move(self.current_file_path, archive_full_path)
                print(f"Przeniesiono do archiwum: {archive_full_path}")
                self._archive_zip(archive_full_path)
            except Exception as e:
                print(f"Błąd podczas przenoszenia/archiwizacji: {e}")
        else:
            print(f"Plik {self.current_file_path} nie istnieje, pomijam przenoszenie.")

        self.start()
        print("Rotacja zakończona, rozpoczęto nowy plik logu.")

    def _archive_zip(self, file_path):
        """Archiwizuje plik do formatu ZIP i usuwa oryginalny plik."""
        zip_path = f"{file_path}.zip"
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, os.path.basename(file_path))
            os.remove(file_path)
            print(f"Archiwizowano {file_path} do {zip_path} i usunięto oryginał.")
        except Exception as e:
            print(f"Błąd archiwizacji ZIP dla {file_path}: {e}")

    def delete_old_logs(self):
        """Usuwa stare archiwa ZIP zgodnie z polityką retencji."""
        threshold = datetime.now() - timedelta(days=self.retention_days)
        archive_dir = os.path.join(self.log_dir, "archive")
        print(f"Usuwanie starych logów (starszych niż {self.retention_days} dni) z {archive_dir}...")
        for name in os.listdir(archive_dir):
            path = os.path.join(archive_dir, name)
            if os.path.isfile(path) and path.endswith('.zip'):
                try:
                    date_str = name.split('_')[-1].split('.')[0]
                    file_date = datetime.strptime(date_str, '%Y%m%d%H%M%S')
                except (ValueError, IndexError):
                    file_date = datetime.fromtimestamp(os.path.getmtime(path))

                if file_date < threshold:
                    try:
                        os.remove(path)
                        print(f"Usunięto stary plik archiwum: {name}")
                    except Exception as e:
                        print(f"Błąd podczas usuwania pliku {name}: {e}")
        print("Zakończono usuwanie starych logów.")

    def read_logs(self, start, end, sensor_id=None):
        """
        Pobiera wpisy z logów zadanego zakresu i opcjonalnie konkretnego czujnika,
        zarówno z bieżących plików CSV, jak i z archiwów ZIP.
        """
        for name in os.listdir(self.log_dir):
            path = os.path.join(self.log_dir, name)
            if os.path.isfile(path) and name.endswith(".csv"):
                yield from self._parse_csv(path, start, end, sensor_id)

        archive_dir = os.path.join(self.log_dir, "archive")
        for name in os.listdir(archive_dir):
            path = os.path.join(archive_dir, name)
            if os.path.isfile(path) and name.endswith(".zip"):
                yield from self._parse_zip(path, start, end, sensor_id)

    def _parse_csv(self, path, start, end, sensor_id):
        """Parsuje plik CSV i zwraca wiersze w zadanym zakresie czasowym."""
        try:
            with open(path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = datetime.fromisoformat(row["timestamp"])
                        if start <= ts <= end and (not sensor_id or row["sensor_id"] == sensor_id):
                            yield row
                    except ValueError:
                        print(f"Ostrzeżenie: Nieprawidłowy format timestamp w pliku {path}, wiersz: {row}")
                        continue
        except FileNotFoundError:
            print(f"Ostrzeżenie: Plik CSV nie znaleziony: {path}")
        except Exception as e:
            print(f"Błąd podczas parsowania pliku CSV {path}: {e}")

    def _parse_zip(self, zip_path, start, end, sensor_id):
        """Parsuje plik ZIP zawierający CSV i zwraca wiersze w zadanym zakresie czasowym."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                for name in zipf.namelist():
                    if name.endswith('.csv'):
                        with zipf.open(name) as f:
                            reader = csv.DictReader((line.decode('utf-8') for line in f))
                            for row in reader:
                                try:
                                    ts = datetime.fromisoformat(row["timestamp"])
                                    if start <= ts <= end and (not sensor_id or row["sensor_id"] == sensor_id):
                                        yield row
                                except ValueError:
                                    print(
                                        f"Ostrzeżenie: Nieprawidłowy format timestamp w pliku ZIP {zip_path}, plik {name}, wiersz: {row}")
                                    continue
        except zipfile.BadZipFile:
            print(f"Ostrzeżenie: Plik ZIP jest uszkodzony lub nieprawidłowy: {zip_path}")
        except FileNotFoundError:
            print(f"Ostrzeżenie: Plik ZIP nie znaleziony: {zip_path}")
        except Exception as e:
            print(f"Błąd podczas parsowania pliku ZIP {zip_path}: {e}")


# Upewniamy się, że wszystkie katalogi istnieją
log_dir = 'logs'
archive_dir = os.path.join(log_dir, 'archive')
os.makedirs(log_dir, exist_ok=True)
os.makedirs(archive_dir, exist_ok=True)

## Inicjalizacja loggera
logger = Logger("config.json")
logger.start()

# Inicjalizacja symulowanego czasu
sim_time_manager = SimulatedTime()

# Inicjalizacja czujników
# Częstotliwość 2 oznacza, że odczyt następuje co 2 jednostki symulowanego czasu.
# Ponieważ 2s realne = 30 min symulowanych, a odczyt co 2s realne, to każdy odczyt to 30 min symulowanych.
# Więc frequency=1 oznacza co 1 symulowaną jednostkę czasu (czyli co 30 min symulowanych).
temp_sensor = TemperatureSensor("T1", frequency=1)
humidity_sensor = HumiditySensor("H1", frequency=1)
pressure_sensor = PressureSensor("P1", frequency=1)
light_sensor = LightSensor("L1", frequency=1)

# Wybór trybu: klient lub serwer
is_server = logger.config.get("is_server", False)


# Definicja pętli odczytu sensorów (używana tylko przez klienta w tym scenariuszu)
def sensor_reading_loop(sensors: List[Sensor], callback_func):
    """
    Pętla odczytująca wartości z podanych sensorów i wywołująca callback.
    """
    for sensor in sensors:
        sensor.register_callback(callback_func)  # Rejestruj callback dla każdego sensora

    try:
        while True:
            for sensor in sensors:
                sensor.read_value()  # Odczytaj wartość (callback zostanie wywołany wewnątrz)

            # Po odczycie wszystkich sensorów, przesuwamy symulowany czas o 30 minut (2s realne)
            sim_time_manager.advance_time(2)
            time.sleep(2)  # Odczekaj 2 sekundy rzeczywistego czasu
    except KeyboardInterrupt:
        print("Zatrzymano pętlę odczytu czujników.")


if is_server:
    print("[INFO] Uruchamianie jako SERWER Z GUI")
    # TYLKO uruchamiamy GUI, które samo zainicjuje swój SensorServer
    root = tk.Tk()
    app = SensorServerGUI(root)  # To uruchamia SensorServer w osobnym wątku
    root.mainloop()  # To uruchamia główną pętlę Tkinter

    # WAŻNE: Tutaj NIE WOLNO wywoływać NetworkServer().start()
    # ponieważ GUI już obsługuje rolę serwera.

else:  # Tryb klienta
    print("[INFO] Uruchamianie jako KLIENT")
    client = NetworkClient()

    try:
        client.connect()
        print("[INFO] Klient połączony z serwerem.")
    except ConnectionError as e:
        print(f"[ERROR] Nie udało się połączyć z serwerem: {e}")
        logger.stop()
        exit(1)


    # Callback logujący i wysyłający do serwera
    def send_and_log(sensor_id, timestamp, value, unit):
        """
        Funkcja wywoływana przez sensory. Loguje odczyt lokalnie i wysyła go do serwera.
        timestamp to teraz symulowany czas.
        """
        logger.log_reading(sensor_id, timestamp, value, unit)
        print(f"[CLIENT] Wysyłam dane: {sensor_id}, {value}{unit} o czasie symulowanym: {timestamp}")
        success = client.send({
            "sensor_id": sensor_id,
            "timestamp": timestamp.isoformat(),  # Wysyłamy symulowany czas
            "value": value,
            "unit": unit
        })
        if not success:
            print(f"[CLIENT ERROR] Nie udało się wysłać danych dla {sensor_id}.")


    # Lista sensorów do przekazania do pętli
    all_sensors = [temp_sensor, humidity_sensor, pressure_sensor, light_sensor]

    try:  # Dodano blok try-finally
        # Uruchom pętlę odczytu sensorów i wysyłania danych
        sensor_reading_loop(all_sensors, send_and_log)
    finally:
        # Po zakończeniu pętli (np. przez KeyboardInterrupt), zamknij połączenie klienta
        client.close()
        print("[INFO] Klient rozłączony.")

# Zakończenie logowania, rotacja pliku (wykonywane po zakończeniu działania klienta/serwera GUI)
logger.stop()
print("[INFO] Logger zatrzymany.")

# --- Logika archiwizacji i usuwania starych logów (wykonywana po zakończeniu obu trybów) ---
# Po zakończeniu procesu powinny być już pliki ZIP w katalogu 'archive'
archived_files = os.listdir(archive_dir)
print(f"Pliki archiwalne: {archived_files}")

# Usuwanie starych logów (starszych niż 30 dni)
logger.delete_old_logs()

# Potwierdzenie, że archiwalne pliki zostały usunięte
archived_files_after_deletion = os.listdir(archive_dir)
print(f"Pliki archiwalne po usunięciu: {archived_files_after_deletion}")

