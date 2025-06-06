# py2025-project-v1

## Opis projektu
System symulujący działanie czujników (np. temperatury, wilgotności, ciśnienia) w środowisku monitoringu.  
Projekt obejmuje:
- Generowanie danych w czasie rzeczywistym,
- Zapisywanie ich na dysku,
- Analizę i wizualizację wyników,
- Udostępnianie danych przez komunikację sieciową,
- Graficzny interfejs użytkownika (GUI).

---

## Instrukcja obsługi

### **Konfiguracja**
1. Utwórz dwa projekty: **serwer** oraz **klient**.
2. W katalogu głównym edytuj plik `config.json`:
   - Dla **serwera** ustaw:
     ```json
     {"is_server": true}
     ```
   - Dla **klienta** ustaw:
     ```json
     {"is_server": false}
     ```

### **Uruchamianie systemu**
1. **Serwer**
