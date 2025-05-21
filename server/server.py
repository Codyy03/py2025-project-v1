import socket
import json
import sys
import yaml
from typing import Optional
from socket import socket as SocketType

class NetworkServer:
    def __init__(self, port: Optional[int] = None):
        """Inicjalizuje serwer na wskazanym porcie."""
        self.port = port or self._load_port_from_config()

    def _load_port_from_config(self) -> int:
        try:
            with open("config.yaml", "r") as f:
                config = yaml.safe_load(f)
                return config.get("port", 5000)
        except Exception as e:
            print(f"Nie można wczytać portu z config.yaml: {e}", file=sys.stderr)
            return 5000  # port domyślny

    def start(self) -> None:
        """Uruchamia nasłuchiwanie połączeń i obsługę klientów."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.bind(("", self.port))
            server_sock.listen(5)
            print(f"Serwer nasłuchuje na porcie {self.port}...")

            while True:
                try:
                    client_sock, addr = server_sock.accept()
                    print(f"\n🔌 Połączenie od {addr}")
                    self._handle_client(client_sock)
                except KeyboardInterrupt:
                    print("\nZatrzymano serwer.")
                    break
                except Exception as e:
                    print(f"Błąd serwera: {e}", file=sys.stderr)

    def _handle_client(self, client_socket: SocketType) -> None:
        with client_socket:
            buffer = ""
            try:
                while True:
                    chunk = client_socket.recv(1024).decode("utf-8")
                    if not chunk:
                        break
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        try:
                            parsed = json.loads(line)
                            print("📨 Odebrano dane:")
                            for key, value in parsed.items():
                                print(f"  {key}: {value}")
                            client_socket.sendall(b"ACK")
                        except json.JSONDecodeError as e:
                            print(f"Błąd JSON: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Błąd obsługi klienta: {e}", file=sys.stderr)


