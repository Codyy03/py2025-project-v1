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

# === Serwer TCP ===
import socket
import json


class SensorServer(threading.Thread):
    """
    Klasa SensorServer uruchamia serwer TCP w osobnym wątku,
    aby nie blokować głównego wątku GUI. Obsługuje wiele połączeń
    klientów, przetwarzając dane i wysyłając potwierdzenia (ACK).
    """

    def __init__(self, port, data_callback, error_callback):
        super().__init__(daemon=True)  # Ustaw wątek jako demon, aby zakończył się z głównym programem
        self.port = port
        self.data_callback = data_callback  # Funkcja do przekazywania danych do GUI
        self.error_callback = error_callback  # Funkcja do przekazywania błędów do GUI
        self.running = False  # Flaga kontrolująca cykl życia wątku serwera
        self.sock = None  # Gniazdo serwera

    def run(self):
        """
        Główna pętla wątku serwera. Inicjalizuje gniazdo, nasłuchuje
        na połączenia i dla każdego klienta uruchamia osobny wątek obsługi.
        """
        try:
            self.running = True
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind(('0.0.0.0', self.port))
            self.sock.listen(5)  # Maksymalna liczba oczekujących połączeń
            self.sock.settimeout(1.0)  # Timeout dla metody accept(), aby wątek mógł sprawdzić self.running

            print(f"GUI Server: Nasłuchiwanie na porcie {self.port}...")

            while self.running:
                try:
                    conn, addr = self.sock.accept()  # Akceptuj nowe połączenie
                    print(f"🔌 GUI Server: Połączenie od {addr}")
                    # Obsługuj klienta w osobnym wątku, aby nie blokować głównego wątku accept()
                    client_handler = threading.Thread(target=self._handle_client, args=(conn, addr))
                    client_handler.daemon = True  # Wątek obsługi klienta również jako demon
                    client_handler.start()

                except socket.timeout:
                    # Brak nowych połączeń w ciągu 1 sekundy, kontynuuj nasłuchiwanie
                    continue
                except Exception as e:
                    # Zgłoś błąd akceptowania połączenia
                    self.error_callback(f"Błąd serwera (accept): {e}")
        except Exception as e:
            # Zgłoś błąd inicjalizacji serwera
            self.error_callback(f"Błąd inicjalizacji serwera GUI: {e}")
        finally:
            # Upewnij się, że gniazdo serwera jest zamknięte po zakończeniu działania
            if self.sock:
                self.sock.close()
            print("GUI Server: Serwer zatrzymany.")

    def _handle_client(self, client_socket: socket.socket, addr):
        """
        Obsługuje pojedyncze połączenie klienta. Odczytuje dane, przetwarza je
        i wysyła potwierdzenie (ACK). Utrzymuje połączenie, dopóki klient się
        nie rozłączy lub serwer nie zostanie zatrzymany.
        """
        buffer = ""  # Bufor do przechowywania niekompletnych wiadomości
        client_socket.settimeout(1.0)  # Timeout dla metody recv()

        try:
            while True:
                try:
                    # Odbierz dane z gniazda klienta
                    chunk = client_socket.recv(1024).decode("utf-8")
                except socket.timeout:
                    # Brak danych w ramach timeoutu, sprawdź, czy serwer nadal działa
                    if not self.running:
                        break  # Serwer się zamyka, zakończ obsługę klienta
                    continue  # Brak danych, kontynuuj pętlę w oczekiwaniu na dane

                if not chunk:
                    # Klient się rozłączył (gniazdo zostało zamknięte z drugiej strony)
                    print(f"GUI Server: Klient {addr} rozłączył się.")
                    break  # Wyjdź z pętli obsługującej klienta

                buffer += chunk  # Dodaj odebrany fragment do bufora

                # Przetwarzaj wszystkie pełne wiadomości zakończone znakiem nowej linii
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)  # Podziel bufor na linię i resztę
                    try:
                        parsed = json.loads(line)  # Deserializuj linię JSON
                        print(f"GUI Server: Odebrano dane od {addr}: {parsed}")
                        self.data_callback(parsed)  # Przekaż dane do GUI
                        client_socket.sendall(b"ACK\n")  # Wyślij ACK z powrotem do klienta (ważne: \n)
                    except json.JSONDecodeError as e:
                        # Zgłoś błąd dekodowania JSON
                        self.error_callback(f"Błąd JSON od klienta {addr}: {e}")
                    except Exception as e:
                        # Zgłoś inny błąd przetwarzania danych
                        self.error_callback(f"Błąd przetwarzania danych od klienta {addr}: {e}")
        except Exception as e:
            self.error_callback(f"Błąd obsługi klienta {addr}: {e}")
        finally:
            # Upewnij się, że gniazdo klienta jest zamknięte po zakończeniu obsługi
            client_socket.close()


class SensorDataBuffer:
    """
    Klasa bufora danych sensorów. Przechowuje odczyty w pamięci i
    udostępnia metody do pobierania najnowszych wartości oraz średnich
    z różnych przedziałów czasowych.
    """

    def __init__(self):
        self.data = {}  # Słownik: {sensor_id: [(timestamp, value, unit)]}
        self.lock = threading.Lock()  # Blokada do bezpiecznego dostępu z wielu wątków
        self.max_history_length = 100  # Maksymalna liczba odczytów do przechowywania dla każdego sensora

    def add_reading(self, msg):
        """
        Dodaje odczyt do bufora. Akceptuje cały słownik wiadomości JSON.
        """
        try:
            sensor_id = msg.get("sensor") or msg.get("sensor_id")
            timestamp_str = msg.get("timestamp")
            value = float(msg.get("value"))
            unit = msg.get("unit")

            # Użyj timestamp z wiadomości, jeśli dostępny, w przeciwnym razie aktualny czas
            timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

            with self.lock:
                if sensor_id not in self.data:
                    self.data[sensor_id] = []
                self.data[sensor_id].append((timestamp, value, unit))

                # Ogranicz bufor do maksymalnej liczby odczytów
                if len(self.data[sensor_id]) > self.max_history_length:
                    self.data[sensor_id] = self.data[sensor_id][-self.max_history_length:]

        except (ValueError, TypeError) as e:
            print(f"Błąd parsowania danych w SensorDataBuffer: {msg} - {e}")
        except Exception as e:
            print(f"Nieoczekiwany błąd w add_reading: {e}")

    def get_latest(self, sensor_id):
        """Zwraca najnowszy odczyt dla danego sensora."""
        with self.lock:
            if sensor_id in self.data and self.data[sensor_id]:
                return self.data[sensor_id][-1]  # Zwróć ostatni element
            return None, None, None  # Zwracaj None dla wszystkich wartości, jeśli brak danych

    def get_avg_last_n_readings(self, sensor_id, n_readings):
        """
        Oblicza średnią wartość dla danego sensora z ostatnich 'n_readings' odczytów.
        """
        with self.lock:
            if sensor_id not in self.data:
                return None

            # Pobierz ostatnie N odczytów
            relevant_readings = self.data[sensor_id][-n_readings:]

            # Wyodrębnij tylko wartości
            values = [val for ts, val, u in relevant_readings]

            if values:
                return sum(values) / len(values)
            return None  # Zwróć None, jeśli nie ma odpowiednich odczytów


class SensorServerGUI:
    """
    Główna klasa interfejsu użytkownika (GUI) dla serwera sensorów.
    Zarządza widokiem, uruchamia SensorServer i aktualizuje tabelę danych.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Sensor Monitor GUI")
        self.root.geometry("800x600")  # Ustaw początkowy rozmiar okna

        self.server = None  # Serwer nie jest uruchamiany automatycznie przy inicjalizacji GUI
        self.buffer = SensorDataBuffer()  # Bufor do przechowywania danych sensorów
        self.queue = queue.Queue()  # Kolejka do bezpiecznego przekazywania aktualizacji do GUI z wątków serwera

        self.port_var = tk.StringVar()  # Zmienna do przechowywania wartości portu
        self._load_port_from_config()  # Wczytaj port z pliku konfiguracyjnego

        self.create_widgets()  # Utwórz elementy interfejsu
        self.update_table()  # Rozpocznij cykliczne odświeżanie tabeli

        # Zarejestruj funkcję do wywołania przy próbie zamknięcia okna
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Wątek do okresowej aktualizacji statusu serwera (startuje z przyciskiem Start)
        self.update_status_thread = None

    def _load_port_from_config(self) -> int:
        """Wczytuje port z pliku konfiguracyjnego lub zwraca domyślny."""
        try:
            with open(CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f)
                port = config.get("port", DEFAULT_PORT)
                self.port_var.set(str(port))  # Ustaw wartość w zmiennej StringVar
                return port
        except Exception as e:
            messagebox.showwarning("Błąd konfiguracji",
                                   f"Nie można wczytać portu z {CONFIG_FILE}: {e}. Użycie portu domyślnego {DEFAULT_PORT}.")
            self.port_var.set(str(DEFAULT_PORT))  # Ustaw domyślny port w zmiennej StringVar
            return DEFAULT_PORT

    def _save_port_to_config(self):
        """Zapisuje aktualny port do pliku konfiguracyjnego."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump({"port": int(self.port_var.get())}, f)
        except Exception as e:
            messagebox.showerror("Błąd zapisu konfiguracji", f"Nie można zapisać portu do {CONFIG_FILE}: {e}")

    def create_widgets(self):
        """Tworzy i rozmieszcza elementy GUI."""
        # Górny panel (Port, Start, Stop)
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text="Port:").pack(side="left", padx=(0, 5))
        self.port_entry = ttk.Entry(top_frame, textvariable=self.port_var, width=8)
        self.port_entry.pack(side="left", padx=(0, 10))

        self.start_btn = ttk.Button(top_frame, text="Start", command=self.start_server)
        self.start_btn.pack(side="left", padx=(0, 5))

        self.stop_btn = ttk.Button(top_frame, text="Stop", command=self.stop_server, state="disabled")
        self.stop_btn.pack(side="left")

        # Pasek statusu (na dole okna)
        status_frame = ttk.Frame(self.root, padding="10")
        status_frame.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Status: Zatrzymany")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief="sunken", anchor="w")
        status_label.pack(fill="x")

        # Tabela (Treeview) do wyświetlania danych sensorów (środkowa część)
        columns = ("Wartość", "Jednostka", "Czas", "Średnia (ostatni odczyt)", "Średnia (12 ostatnich odczytów)")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        # Nagłówki kolumn tabeli
        self.tree.heading("#0", text="Sensor ID")
        self.tree.heading("Wartość", text="Wartość")
        self.tree.heading("Jednostka", text="Jednostka")
        self.tree.heading("Czas", text="Czas")
        self.tree.heading("Średnia (ostatni odczyt)", text="Średnia (ost. odczyt)")  # Zmieniona nazwa
        self.tree.heading("Średnia (12 ostatnich odczytów)", text="Średnia (12 ost. odczytów)")  # Zmieniona nazwa

        # Szerokość kolumn tabeli
        self.tree.column("#0", width=100, anchor="w")
        self.tree.column("Wartość", width=100, anchor="center")
        self.tree.column("Jednostka", width=80, anchor="center")
        self.tree.column("Czas", width=160, anchor="center")
        self.tree.column("Średnia (ostatni odczyt)", width=160, anchor="center")  # Zmieniona szerokość
        self.tree.column("Średnia (12 ostatnich odczytów)", width=160, anchor="center")  # Zmieniona szerokość

    def start_server(self):
        """Uruchamia wątek serwera TCP."""
        if self.server and self.server.running:
            return  # Serwer już działa

        try:
            port = int(self.port_var.get())
            self._save_port_to_config()  # Zapisz port przed uruchomieniem

            self.server = SensorServer(port, self.handle_data_from_server_thread, self.handle_error)
            self.server.start()  # Uruchom wątek serwera
            self.status_var.set(f"Status: Nasłuchiwanie na porcie {port}...")
            self.start_btn["state"] = "disabled"
            self.stop_btn["state"] = "normal"
            self.port_entry["state"] = "disabled"  # Zablokuj edycję portu po starcie

            # Uruchom wątek aktualizacji statusu, jeśli jeszcze nie działa
            if not self.update_status_thread or not self.update_status_thread.is_alive():
                self.update_status_thread = threading.Thread(target=self._update_status_periodically, daemon=True)
                self.update_status_thread.start()

        except ValueError:
            messagebox.showerror("Błąd portu", "Port musi być liczbą całkowitą.")
            self.status_var.set("Status: Błąd portu")
        except Exception as e:
            messagebox.showerror("Błąd uruchomienia serwera", f"Nie można uruchomić serwera: {e}")
            self.status_var.set("Status: Błąd")

    def stop_server(self):
        """Zatrzymuje wątek serwera TCP."""
        if self.server:
            self.server.running = False  # Ustaw flagę zatrzymania dla wątku serwera
            self.server.join(timeout=3)  # Poczekaj na zakończenie wątku serwera
            self.server = None  # Usuń referencję do serwera

            # Wątek aktualizacji statusu jest daemonem i zakończy się wraz z self.server.running=False
            # i zakończeniem pętli w _update_status_periodically.

        self.status_var.set("Status: Zatrzymany")
        self.start_btn["state"] = "normal"
        self.stop_btn["state"] = "disabled"
        self.port_entry["state"] = "normal"  # Odblokuj edycję portu

    def handle_data_from_server_thread(self, msg):
        """
        Metoda wywoływana z wątku serwera do aktualizacji danych.
        Umieszcza dane w buforze i sygnalizuje GUI, że dane są gotowe do wyświetlenia.
        """
        self.buffer.add_reading(msg)  # Dodaj całą wiadomość do bufora
        sensor_id = msg.get("sensor") or msg.get("sensor_id")
        if sensor_id:
            self.queue.put(sensor_id)  # Umieść ID sensora w kolejce GUI

    def handle_error(self, err):
        """
        Obsługuje błędy zgłoszone przez wątek serwera.
        Aktualizuje pasek statusu GUI w sposób bezpieczny dla wątków.
        """
        self.root.after(0, lambda: self.status_var.set(f"Status: błąd - {err}"))

    def _update_status_periodically(self):
        """
        Wątek pomocniczy do okresowej aktualizacji statusu serwera na GUI.
        """
        while self.server and self.server.running:  # Sprawdzaj, czy serwer istnieje i działa
            if self.server.sock:
                self.root.after(0,
                                lambda: self.status_var.set(f"Status: Nasłuchiwanie na porcie {self.server.port}..."))
            time.sleep(5)  # Odświeżaj status co 5 sekund
        # Gdy serwer się zatrzyma (lub self.server stanie się None), zaktualizuj status na "Zatrzymany"
        self.root.after(0, lambda: self.status_var.set("Status: Zatrzymany"))

    def update_table(self):
        """
        Cyklicznie odświeża dane w tabeli GUI na podstawie danych z bufora.
        Pobiera zaktualizowane sensory z kolejki.
        """
        updated_sensors = set()
        while not self.queue.empty():
            updated_sensors.add(self.queue.get())

        for sensor_id in updated_sensors:
            latest_ts, latest_val, latest_unit = self.buffer.get_latest(sensor_id)

            # "Średnia za 1h" = aktualizacja danych po wysłaniu nowych danych przez klienta, czyli ostatni odczyt
            avg_last_reading = latest_val

            # "Średnia za 12h" = średnia z ostatnich 12 odświeżeń (odczytów)
            avg_last_12_readings = self.buffer.get_avg_last_n_readings(sensor_id, 12)

            # Formatuj wartości do wyświetlenia, używając "N/A" dla brakujących danych
            values = (
                f"{latest_val:.2f}" if latest_val is not None else "N/A",
                latest_unit or "N/A",
                latest_ts.strftime('%Y-%m-%d %H:%M:%S') if latest_ts else "N/A",
                f"{avg_last_reading:.2f}" if avg_last_reading is not None else "N/A",
                f"{avg_last_12_readings:.2f}" if avg_last_12_readings is not None else "N/A"
            )

            # Zaktualizuj istniejący wiersz lub wstaw nowy
            if sensor_id in self.tree.get_children():
                self.tree.item(sensor_id, values=values)
            else:
                self.tree.insert("", "end", iid=sensor_id, text=sensor_id, values=values)

        self.root.after(1000, self.update_table)  # Zaplanuj kolejne odświeżenie za 1 sekundę

    def on_closing(self):
        """
        Obsługuje zdarzenie zamknięcia okna GUI.
        Zatrzymuje wątek serwera i zamyka aplikację.
        """
        if messagebox.askokcancel("Zamknij", "Czy na pewno chcesz zamknąć aplikację?"):
            self._save_port_to_config()  # Zapisz port przed zamknięciem
            self.stop_server()  # Zatrzymanie serwera

            self.root.destroy()  # Zniszcz okno Tkinter


# Jeśli ten plik jest uruchamiany bezpośrednio (do testów GUI)
if __name__ == '__main__':
    root = tk.Tk()
    app = SensorServerGUI(root)
    root.mainloop()

