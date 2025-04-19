import math
from datetime import datetime
from itertools import cycle
import  numpy as np
import time
import  threading
import random

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

    def read_value(self):
        """
        Symuluje pobranie odczytu z czujnika.
        W klasie bazowej zwraca losową wartość z przedziału [min_value, max_value].
        """
        if not self.active:
            raise Exception(f"Czujnik {self.name} jest wyłączony.")

        value = random.uniform(self.min_value, self.max_value)
        self.last_value = value
        return value

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

    def __str__(self):
        return f"Sensor(id={self.sensor_id}, name={self.name}, unit={self.unit})"


class TemperatureSensor(Sensor):
    def __init__(self,sensor_id,name="Czujnik temperatury",unit = "°C", min_value = -20, max_value = 50, frequency = 2):
        super().__init__(sensor_id,name,unit,min_value,max_value,frequency)


    # symulacja temperatury z uwzglednienem cyklu dziennego
    def read_value(self):
        return  super().read_value()

class HumiditySensor(Sensor):
        def __init__(self, sensor_id, name="Czujnik wilgotności", unit="%", min_value=0, max_value=100, frequency=2):
            super().__init__(sensor_id, name, unit, min_value, max_value, frequency)

        def read_value(self, temperature=None):
            if not self.active:
                raise Exception(f"Czujnik {self.name} jest wyłączony.")

            now = datetime.now().date()
            difference = now -self.last_date

            if difference.total_seconds() > self.frequency:
                self.last_date = now
                return super().read_value()
            return self.last_value

            #Uwzględnia wpływ temperatury – gdy podamy wartość temperatury, wilgotność spada przy wysokiej temperaturze i wzrasta przy niskiej.
            temp_factor = 0
            if temperature  is not None:
                temp_factor = max(-10, min(10, (25 - temperature)*0.5))

            humidity = random.uniform(self.min_value, self.max_value) + temp_factor
            humidity = max(self.min_value, min(self.max_value, humidity))

            self.last_value = round(humidity, 2)
            return self.last_value
