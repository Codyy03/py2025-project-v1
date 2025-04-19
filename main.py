from datetime import datetime
import random
import numpy as np

class Sensor:
    def __init__(self, sensor_id, name, unit, min_value, max_value, frequency=1):
        """
        Inicjalizacja czujnika.

        :param sensor_id: Unikalny identyfikator czujnika
        :param name: Nazwa lub opis czujnika
        :param unit: Jednostka miary (np. '°C', '%', 'hPa', 'lux')
        :param min_value: Minimalna wartość odczytu
        :param max_value: Maksymalna wartość odczytu
        :param frequency: Częstotliwość odczytów (sekundy)
        """
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

    def read_value(self):
        """
        Symuluje pobranie odczytu z czujnika.
        W klasie bazowej zwraca losową wartość z przedziału [min_value, max_value].
        """
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        now = datetime.now()

        if (now - self.last_read_time).total_seconds() >= self.frequency:
            value = random.uniform(self.min_value, self.max_value)
            self.last_value = value
            self.history.append((now,value))
            self.last_read_time = now
            return self.last_value

    def calibrate(self, calibration_factor):
        """
        Kalibruje ostatni odczyt przez przemnożenie go przez calibration_factor.
        Jeśli nie wykonano jeszcze odczytu, wykonuje go najpierw.
        """
        if self.last_value is None:
            self.read_value()

        self.last_value *= calibration_factor
        return self.last_value

    def get_last_value(self):
        """
        Zwraca ostatnią wygenerowaną wartość, jeśli była wygenerowana.
        """
        if self.last_value is None:
            return self.read_value()
        return self.last_value

    def start(self):
        """
        Włącza czujnik.
        """
        self.active = True

    def stop(self):
        """
        Wyłącza czujnik.
        """
        self.active = False

    def get_history(self):
        return self.history

    def __str__(self):
        return f"Sensor(id={self.sensor_id}, name={self.name}, unit={self.unit})"


class TemperatureSensor(Sensor):
    def __init__(self,sensor_id,name="Czujnik temperatury",unit = "°C", min_value = -20, max_value = 50, frequency = 2):
        super().__init__(sensor_id,name,unit,min_value,max_value,frequency)


    # symulacja temperatury z uwzglednienem cyklu dziennego
    def read_value(self):
        # Symulacja temperatury:
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        value = np.random.uniform(self.min_value, self.max_value)  # Losowa wartość z zakresu min_value - max_value
        self.last_value = round(value, 2)  # Zaokrąglamy do 2 miejsc po przecinku
        self.history.append((datetime.now(), self.last_value))  # Zapisujemy wartość do historii
        return self.last_value

class HumiditySensor(Sensor):
        def __init__(self, sensor_id, name="Czujnik wilgotności", unit="%", min_value=0, max_value=100, frequency=2):
            super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

        def read_value(self, temperature=None):
            # Symulacja wilgotności:
            # Generuje losową wartość z zakresu (0%–100%).
            # Jeśli podana jest temperatura, wilgotność jest modyfikowana (spada przy wysokich temperaturach i wzrasta przy niskich).
            if not self.active:
                raise Exception(f"Czujnik {self.name} jest wyłączony.")
            temp_factor = 0
            if temperature is not None:
                temp_factor = max(-10, min(10, (25 - temperature) * 0.5))
            humidity = random.uniform(self.min_value, self.max_value) + temp_factor
            humidity = max(self.min_value, min(self.max_value, humidity))
            self.last_value = round(humidity, 2)
            self.history.append((datetime.now(), self.last_value))
            return self.last_value

class PressureSensor(Sensor):
    def __init__(self, sensor_id, name="Czujnik ciśnienia", unit="hPa", min_value=950, max_value=1050, frequency=2):
        super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

    def read_value(self):
        # Symulacja ciśnienia atmosferycznego:
        # Generuje wartość w oparciu o rozkład normalny (środek zakresu jako średnia, odchylenie standardowe wynosi 5).
        # Wartość jest zaokrąglana do dwóch miejsc po przecinku.
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")
        pressure = random.gauss((self.min_value + self.max_value) / 2, 5)  # Symulacja z fluktuacjami
        pressure = max(self.min_value, min(self.max_value, pressure))
        self.last_value = round(pressure, 2)
        self.history.append((datetime.now(), self.last_value))
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



