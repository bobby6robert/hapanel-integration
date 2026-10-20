# HA Panel

Lekka, darmowa alternatywa dla Fully Kiosk Browser do obsługi Home Assistanta na tablecie ściennym, razem z własną integracją HA. Powstała z myślą o Lenovo Tab M10 FHD Plus (TB-X606F, Android 10), ale działa na Androidzie 8 i nowszym.

Repozytorium zawiera dwie części:

| Część | Folder | Do czego |
|---|---|---|
| Aplikacja na Androida | `app/` | Kiosk z WebView, serwer HTTP, czujniki, wykrywanie ruchu |
| Integracja Home Assistant | `custom_components/hapanel/` | Encje i sterowanie tabletem z poziomu HA |

## Funkcje aplikacji

- Pełnoekranowy WebView z dashboardem HA, ekran zawsze włączony, automatyczne ponawianie po błędzie sieci.
- Autostart po restarcie tabletu, opcjonalnie jako domyślny launcher.
- Blokada wyjścia (przypięcie aplikacji). Ustawienia otwierasz 5 szybkimi dotknięciami w lewym górnym rogu.
- Serwer HTTP na porcie 8765 do sterowania z HA.
- Odczyt baterii, ładowania i czujnika światła.
- Wykrywanie ruchu z przedniej kamery, wybudzanie ekranu i usypianie po bezczynności.
- Automatyczna jasność z czujnika światła.
- Odczytywanie komunikatów na głos (TTS).
- Brak zewnętrznych zależności.

"Uśpienie" ekranu to czarna nakładka z minimalną jasnością. Bez roota Android nie pozwala naprawdę wyłączyć ekranu.

## Budowanie APK

Workflow w `.github/workflows` buduje debugowy APK po każdym commicie.

1. Wejdź w zakładkę **Actions** i otwórz ostatnie uruchomienie.
2. Na dole, w sekcji **Artifacts**, pobierz `hapanel-apk` i rozpakuj plik `app-debug.apk`.

Możesz też otworzyć projekt w Android Studio (Build → Build APK).

## Instalacja na tablecie

1. Skopiuj `app-debug.apk` na tablet (Dysk Google, e-mail, kabel USB) albo zainstaluj przez `adb install -r app-debug.apk`.
2. Zezwól na instalację z nieznanych źródeł.
3. Uruchom **HA Panel** i wpisz adres dashboardu, np. `http://IP_HA:8123/lovelace/0`.
4. Dla autostartu kliknij w ustawieniach "Zezwól na autostart" (wyświetlanie nad innymi aplikacjami) i wyłącz optymalizację baterii dla aplikacji.
5. Funkcje dodatkowe (ruch z kamery, auto-jasność) włączaj po sprawdzeniu podstawowej wersji.

## Integracja Home Assistant

1. Skopiuj folder `custom_components/hapanel` do `/config/custom_components/` w HA i zrestartuj HA.
2. Ustawienia → Urządzenia i usługi → Dodaj integrację → **HA Panel**.
3. Podaj adres IP tabletu, port `8765` i token API (jeśli ustawiony w aplikacji).

Wymaga Home Assistanta 2024.5 lub nowszego. Integracja odpytuje tablet co 15 s.

### Encje

| Typ | Encja |
|---|---|
| Czujnik | bateria, światło |
| Czujnik binarny | ładowanie, ruch, ekran włączony |
| Przełącznik | ekran (budzenie/uśpienie), automatyczna jasność |
| Liczba | jasność (0-255) |
| Przycisk | odśwież dashboard |
| Tekst | załaduj adres (otwiera adres w panelu) |
| Powiadomienie | komunikat głosowy (`notify.send_message`) |

Przy używaniu integracji zostaw w aplikacji **puste** pola adresu HA i tokena. Wypychanie stanów utworzyłoby zdublowane encje.

## Alternatywa bez integracji: REST API i `rest_command`

Aplikacja udostępnia endpointy GET (jeśli ustawisz token API, dopisz `token=...`):

| Endpoint | Działanie |
|---|---|
| `/status` | stan w JSON |
| `/wake`, `/sleep` | wybudzenie, uśpienie ekranu |
| `/brightness?value=0-255` | jasność (wyłącza auto-jasność) |
| `/auto?on=1\|0` | automatyczna jasność |
| `/load?url=...` | załaduj adres |
| `/reload` | odśwież stronę |
| `/tts?text=...` | odczytaj komunikat |

```yaml
rest_command:
  tablet_wake:   { url: "http://IP_TABLETU:8765/wake" }
  tablet_sleep:  { url: "http://IP_TABLETU:8765/sleep" }
  tablet_reload: { url: "http://IP_TABLETU:8765/reload" }
  tablet_brightness:
    url: "http://IP_TABLETU:8765/brightness?value={{ value }}"
  tablet_tts:
    url: "http://IP_TABLETU:8765/tts?text={{ text | urlencode }}"
```

Jeśli nie używasz integracji, możesz wpisać w aplikacji adres HA i long-lived token. Wtedy aplikacja sama utworzy w HA encje `sensor.tablet_battery`, `binary_sensor.tablet_charging`, `binary_sensor.tablet_motion`, `binary_sensor.tablet_screen` i `sensor.tablet_illuminance` (raport co 30 s).

## Ochrona baterii przy pracy 24/7

Ładowanie przez gniazdko smart, włączane poniżej 25% i wyłączane powyżej 80%, wydłuża życie baterii:

```yaml
automation:
  - alias: Tablet - ładuj
    trigger: { platform: numeric_state, entity_id: sensor.tablet_battery, below: 25 }
    action: { service: switch.turn_on, target: { entity_id: switch.gniazdko_tablet } }
  - alias: Tablet - przestań ładować
    trigger: { platform: numeric_state, entity_id: sensor.tablet_battery, above: 80 }
    action: { service: switch.turn_off, target: { entity_id: switch.gniazdko_tablet } }
```

Nazwy encji dopasuj do swojej instalacji.

## Bezpieczeństwo

API tabletu nie jest szyfrowane. Używaj go wyłącznie w sieci lokalnej, ustaw token API i nie wystawiaj portu 8765 do internetu. Zdalny dostęp rób przez VPN.

## Struktura repozytorium

```
app/                          aplikacja Android (Kotlin, bez zależności)
custom_components/hapanel/    integracja Home Assistant
.github/workflows/            budowanie APK
```
