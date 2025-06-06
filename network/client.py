import socket
import json
import time
import yaml
from typing import Optional


class NetworkClient:
    def __init__(
        self,
        config_path: str = "config.yaml",
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None
    ):
        """Inicjalizuje klienta sieciowego na podstawie config.yaml."""
        config = self._load_config(config_path)

        self.host = host or config.get("host", "127.0.0.1")
        self.port = port or config.get("port", 5000)
        self.timeout = timeout or config.get("timeout", 5.0)
        self.retries = retries or config.get("retries", 3)
        self.sock: Optional[socket.socket] = None

    def _load_config(self, path: str) -> dict:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Błąd wczytywania pliku konfiguracyjnego: {e}")
            return {}

    def connect(self) -> None:
        """Nawiązuje połączenie z serwerem."""
        for attempt in range(1, self.retries + 1):
            try:
                self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                return
            except socket.error as e:
                print(f"[{attempt}/{self.retries}] Connection failed: {e}")
                time.sleep(1)
        raise ConnectionError(f"Failed to connect after {self.retries} attempts.")

    def send(self, data: dict) -> bool:
        if not self.sock:
            raise ConnectionError("Socket not connected. Call connect() first.")
        try:
            payload = self._serialize(data) + b"\n"  # <-- tutaj dodaj \n
            self.sock.sendall(payload)
            print("[DEBUG] Wysłano dane, oczekiwanie na odpowiedź...")

            ack = self.sock.recv(1024)
            print(f"[DEBUG] Otrzymano odpowiedź: {ack}")
            return True
        except socket.timeout:
            print("Send failed: timed out")
            return False
        except socket.error as e:
            print(f"Send failed: {e}")
            return False

    def close(self) -> None:
        """Zamyka połączenie."""
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)  # Grzeczne zamknięcie
            except socket.error:
                pass  # Socket mógł już być zamknięty przez serwer
            finally:
                self.sock.close()
                self.sock = None

    def _serialize(self, data: dict) -> bytes:
        """Zamienia słownik na bajty JSON."""
        return json.dumps(data).encode("utf-8")

    def _deserialize(self, raw: bytes) -> dict:
        """Zamienia bajty JSON na słownik."""
        return json.loads(raw.decode("utf-8"))


if __name__ == "__main__":
    print("[INFO] Uruchamianie jako KLIENT")
    client = NetworkClient()  # Domyślnie wczytuje config.yaml
    try:
        client.connect()
        data = {
            "sensor_id": "T1",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "value": 40.72,
            "unit": "°C"
        }
        success = client.send(data)
        print("✅ Wysłano poprawnie:", success)
    finally:
        client.close()
