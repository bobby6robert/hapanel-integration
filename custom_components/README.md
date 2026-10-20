# HA Panel – własna alternatywa dla Fully Kiosk

Bez zależności zewnętrznych. Android 8+ (testowane założeniowo pod TB-X606F, Android 10).

## Budowanie
**A) Android Studio:** File → Open → folder `hapanel`, poczekaj na sync, Build → Build APK(s).
**B) GitHub:** wrzuć folder do repo; Actions → build → artefakt `hapanel-apk` (debug APK, działa od razu).
Instalacja: `adb install app-debug.apk` lub skopiuj APK na tablet (zezwól na nieznane źródła).

## Pierwsze uruchomienie
1. Wpisz adres dashboardu i (opcjonalnie) adres HA + long-lived token (Profil → Zabezpieczenia → Tokeny).
2. Ustawienia otwierasz 5× dotknięciem lewego górnego rogu (w ciągu 4 s).
3. Kliknij "Zezwól na autostart" i włącz zgodę – bez niej po restarcie tabletu aplikacja sama się nie uruchomi.
4. Wyłącz optymalizację baterii dla aplikacji (Ustawienia Androida → Aplikacje → HA Panel → Bateria).
5. Opcjonalnie: ustaw HA Panel jako domyślny ekran główny (launcher) – wtedy przycisk Home też wraca do panelu.
6. Blokada (przypięcie) przy pierwszym starcie poprosi o potwierdzenie systemowe. Wyjście: przytrzymaj Wstecz+Przegląd.

## Encje tworzone w HA (nazwa urządzenia = `tablet`)
sensor.tablet_battery, binary_sensor.tablet_charging, binary_sensor.tablet_screen,
binary_sensor.tablet_motion, sensor.tablet_illuminance (odświeżane co 30 s i przy zmianie).
Encje tworzone przez API stanów znikają po restarcie HA do czasu następnego raportu (max 30 s).

## API tabletu (GET, port 8765; jeśli ustawiłeś token dodaj `&token=...`)
/load?url=  /reload  /brightness?value=0-255  /auto?on=1|0  /sleep  /wake  /tts?text=  /status

## configuration.yaml
```yaml
rest_command:
  tablet_wake:  { url: "http://IP_TABLETU:8765/wake" }
  tablet_sleep: { url: "http://IP_TABLETU:8765/sleep" }
  tablet_reload: { url: "http://IP_TABLETU:8765/reload" }
  tablet_brightness:
    url: "http://IP_TABLETU:8765/brightness?value={{ value }}"
  tablet_tts:
    url: "http://IP_TABLETU:8765/tts?text={{ text | urlencode }}"
```

## Ładowanie baterii (gniazdko smart)
```yaml
automation:
  - alias: Tablet – ładuj
    trigger: { platform: numeric_state, entity_id: sensor.tablet_battery, below: 25 }
    action: { service: switch.turn_on, target: { entity_id: switch.gniazdko_tablet } }
  - alias: Tablet – przestań ładować
    trigger: { platform: numeric_state, entity_id: sensor.tablet_battery, above: 80 }
    action: { service: switch.turn_off, target: { entity_id: switch.gniazdko_tablet } }
```

## Uwagi
- "Uśpienie" to czarna nakładka + jasność minimalna (bez roota nie da się wyłączyć ekranu naprawdę).
- Ruch: zmniejsz liczbę w "Czułość ruchu" jeśli nie reaguje, zwiększ jeśli wybudza bez powodu.
- API nie ma szyfrowania – używaj tylko w sieci lokalnej i ustaw token API.
