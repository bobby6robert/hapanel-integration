# HA Panel – integracja Home Assistant

Integracja lokalna dla tabletu z aplikacją **[HA Panel](https://github.com/bobby6robert/hapanel-app)** (panel ścienny na Androidzie). Zastępuje integrację Fully Kiosk Browser i nie wymaga płatnej licencji.

## Instalacja

**HACS:** HACS → trzy kropki → Custom repositories → adres tego repozytorium, kategoria *Integration* → pobierz *HA Panel* → restart HA.

**Ręcznie:** skopiuj folder `custom_components/hapanel` do `/config/custom_components/` i zrestartuj HA.

## Konfiguracja

**Automatycznie:** po uruchomieniu aplikacji HA Panel na tablecie w tej samej sieci w Ustawienia → Urządzenia i usługi pojawi się wykryte urządzenie. Kliknij **Skonfiguruj** i wpisz **kod parowania** z ekranu tabletu. Kreator zaproponuje adres dashboardu (z adresu zewnętrznego HA, jeśli jest ustawiony; dla mikrofonu musi to być `https://`), adresy awaryjne, uśpienie, ruch, tryb nocny i opcjonalny PIN do ustawień. Po zatwierdzeniu integracja:
- wyśle ustawienia na tablet (nic nie wpisujesz na urządzeniu),
- sparuje tablet losowym tokenem API (zapisany w HA i na tablecie),
- będzie śledzić zmianę adresu IP tabletu (aktualizuje się sama).

Ustawienia możesz później zmienić w opcjach integracji (zastosują się od razu). Po ponownej instalacji aplikacji tablet jest niesparowany, więc HA pokaże „Wymagana ponowna konfiguracja” z prośbą o nowy kod z ekranu. Po jego wpisaniu ustawienia wracają na tablet. Przycisk „Zastosuj ustawienia na tablecie” wysyła je na żądanie.

PIN do ustawień jest tylko do zapisu: idzie prosto na tablet i nie jest przechowywany w HA, więc po reinstalacji trzeba go ustawić ponownie.

**Ręcznie:** Dodaj integrację → HA Panel → podaj adres IP tabletu (widoczny w ustawieniach aplikacji), port `8765` i nazwę (zalecana **Panel**; nazwa „Tablet” często koliduje z encjami Browser Mod).

Czego nie da się zrobić zdalnie: Android wymaga dotknięcia tabletu, żeby nadać uprawnienie mikrofonu i autostartu oraz wyłączyć optymalizację baterii. Czujnik „Brakujące uprawnienia” pokazuje, co jeszcze trzeba kliknąć na tablecie.

Wymaga Home Assistanta 2024.5 lub nowszego. Integracja odpytuje tablet co 15 s (`local_polling`). Wykrywanie wymaga, żeby HA i tablet były w tej samej sieci (mDNS nie przechodzi przez VLAN-y bez przekaźnika).

## Nowości w 1.5

Połączenie wersji 1.3 i 1.4 w jedną (wymaga aplikacji HA Panel 2.5; starsza aplikacja działa bez nowych funkcji):

- **Zegar nocny z temperaturami i informacją:** w *Konfiguruj* wybierz czujnik temperatury na zewnątrz, w domu oraz encję z krótkim tekstem (np. „Jutro: odpady”). HA wysyła je na tablet tylko przy zmianie.
- **Przełącznik „Tryb nocny”** – wyłączysz zegar np. na czas imprezy; zmiana zapisuje się też w opcjach integracji.
- **Okno podglądu z tytułem:** `hapanel.popup` ma pole `title` (np. „🔔 Ktoś dzwoni do furtki”).
- **Usługa `hapanel.say`:** komunikat głosowy z ustawieniem głośności i wybudzeniem ekranu.
- **Czujnik zbliżeniowy** (jeśli tablet go ma): encja „Zbliżenie”, wybudzanie ręką przy ekranie (opcja w *Konfiguruj*).
- **Nowe encje:** „Zegar nocny” (czy zegar jest teraz na ekranie), „Adres awaryjny” (diagnostyka), przyciski „Zamknij podgląd” i „Sprawdź aktualizacje”.

## Encje

| Typ | Encja |
|---|---|
| Czujnik | bateria, światło; diagnostyczne: temperatura i kondycja baterii, sygnał Wi-Fi, wolna pamięć, czas od uruchomienia, ostatnie załadowanie strony, wersja WebView, adres IP, wersja aplikacji, aktualny adres, brakujące uprawnienia |
| Czujnik binarny | ładowanie, ruch, ekran włączony, pora nocna, zegar nocny, adres awaryjny (diagnostyka), zbliżenie (jeśli tablet ma czujnik) |
| Przełącznik | ekran (budzenie/uśpienie), automatyczna jasność, tryb nocny |
| Liczba | jasność (0-255) |
| Odtwarzacz | dzwonki, komunikaty `tts.speak`, głośność, stop |
| Przycisk | odśwież dashboard, restartuj panel, zatrzymaj dźwięk, zamknij podgląd, zastosuj ustawienia na tablecie, sprawdź aktualizacje |
| Kamera | zrzut ekranu tabletu na żądanie (bez strumienia, więc nie obciąża HA) |
| Aktualizacja | wersja aplikacji z GitHub Releases, instalacja jednym kliknięciem |
| Tekst | aktualny adres panelu (wpisanie nowego ładuje go) |
| Powiadomienie | komunikat głosowy (`notify.send_message`) |

Nazwy encji powstają z nazwy urządzenia, np. `switch.panel_ekran` i `media_player.panel`. Sprawdź je w Narzędziach deweloperskich → Stany.

## Zdarzenia z tabletu (webhook)

Zamiast czekać na odpytywanie (co 15 s), tablet wysyła zdarzenia od razu na webhook, który integracja rejestruje i przekazuje aplikacji przy konfiguracji. Aktualizują stan (ruch, ekran) i publikują zdarzenie `hapanel_event`:

| `event` | Kiedy | Dodatkowe pola |
|---|---|---|
| `motion` | ruch zaczął się lub skończył | `state` (true/false) |
| `touch` | dotknięcie ekranu (najwyżej raz na 10 s) | – |
| `low_battery` | bateria poniżej 15% bez ładowania | `level` |
| `start` | aplikacja wystartowała | `version` |
| `screen` | uśpienie lub zegar nocny włączony/wyłączony | `sleeping`, `clock` |

```yaml
triggers:
  - trigger: event
    event_type: hapanel_event
    event_data: { event: motion, state: true }
```

Webhook nie wymaga tokena HA na tablecie. Adres jest losowy i działa tylko z POST. Tablet musi widzieć adres HA, który integracja poda (wewnętrzny lub zewnętrzny, zależnie od ustawień sieci w HA).

## Ochrona baterii (blueprinty)

Tablet na stałej ładowarce może spuchnąć. W folderze `blueprints/` są dwa gotowe szablony:

- **battery_guard**: ładowanie w zakresie (domyślnie włącz poniżej 20%, wyłącz powyżej 80%) przez gniazdko smart, z kontrolą co 10 minut i po restarcie HA.
- **battery_temperature_alert**: powiadomienie, gdy bateria jest za gorąca przez 5 minut.

Import: Ustawienia → Automatyzacje i sceny → Blueprinty → Importuj blueprint i wklej adres pliku z GitHuba, np. `https://github.com/bobby6robert/hapanel-integration/blob/main/blueprints/automation/hapanel/battery_guard.yaml`. Potem utwórz automatyzację z szablonu (czujnik baterii `sensor.panel_bateria`, gniazdko, progi).

## Usługi

| Usługa | Działanie |
|---|---|
| `hapanel.popup` | pokazuje stronę lub kamerę na wierzchu tabletu (`url`, `seconds`, `wake`, `title`); po czasie wraca do poprzedniego widoku |
| `hapanel.say` | komunikat głosowy na tablecie (`message`, opcjonalnie `volume` 0–100 i `wake`) |
| `hapanel.close_popup` | zamyka okno podglądu |
| `hapanel.export_settings` | zwraca kopię ustawień tabletu (bez PIN-u, tokenów i webhooka) |
| `hapanel.import_settings` | wysyła ustawienia z kopii na tablet (pole `settings`) |

Cel: encja odtwarzacza tabletu (np. `media_player.panel`). Przykład na dzwonek:

```yaml
action: hapanel.popup
target: { entity_id: media_player.panel }
data: { url: "/lovelace/kamera", seconds: 60 }
```

## Przykłady

W folderze `examples/` są szablony automatyzacji (dzwonek przy furtce z wybudzaniem ekranu, alert o niedostępnym tablecie). Zamień w nich nazwy encji na własne.

## Aktualizacje i wydania

- **Integracja** aktualizuje się przez HACS na podstawie wydań (Releases) tego repozytorium. Po zmianie plików podbij `version` w `custom_components/hapanel/manifest.json`, zrób commit i utwórz wydanie z tagiem `vX.Y.Z` zgodnym z tym numerem (Releases → Create a new release). HACS pokaże aktualizację po odświeżeniu danych (trzy kropki → Reload data). Starsze wydania zostają, a w HACS można wybrać wcześniejszą wersję przez „Pobierz ponownie”.
- **Aplikacja** ma w HA encję aktualizacji. HA sprawdza najnowsze wydanie repozytorium `hapanel-app` co 6 godzin, a po kliknięciu **Zainstaluj** tablet pobiera APK z GitHuba i pokazuje systemowe potwierdzenie (jedno dotknięcie). Wymaga zgody „Instalacja aplikacji z tego źródła” w ustawieniach Androida, o co przypomina lista kontrolna w aplikacji.

## Licencja

Dodaj plik `LICENSE` wybranej licencji przed publiczną dystrybucją.
