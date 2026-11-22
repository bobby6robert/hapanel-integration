<img src="images/logo.png" width="96" align="right" alt="RB IT Academy">

# HA Panel – Home Assistant integration

🇵🇱 [Polski](README.md) · 🇬🇧 English

Local integration for tablets running the **[HA Panel](https://github.com/bobby6robert/hapanel-app)** app (Android wall panel). Replaces the Fully Kiosk Browser integration and needs no paid licence. Translations: Polish and English.

## Installation

**HACS:** HACS → three dots → Custom repositories → this repository's URL, category *Integration* → download *HA Panel* → restart HA.

**Manual:** copy `custom_components/hapanel` to `/config/custom_components/` and restart HA.

## Configuration

Start the HA Panel app on a tablet in the same network. A discovered device appears in Settings → Devices & services. Click **Configure** and enter the **pairing code** shown on the tablet. The integration then:
- sends all settings to the tablet (nothing to type on the device),
- pairs the tablet with a random API token,
- follows IP address changes of the tablet.

Change settings later in the integration options; they apply immediately. Settings saved in the tablet menu are written back to the options. Requires Home Assistant 2024.5 or newer; brand icon needs 2026.3+.

## Aurora (voice assistant)

Requires HA Panel 2.7+ (all options below: 2.12+).
- The tablet sends recordings to the integration webhook; the integration does speech-to-text, the conversation agent and text-to-speech.
- Options: reply listening after announcements (off by default), silence when nobody is home, wake-word sensitivity, announcement volume, TV ducking (chosen media player is lowered during `hapanel.say` / `hapanel.converse` and restored afterwards).
- When the tablet recognises a household voice from the “Record Aurora” recordings, the conversation knows who is speaking.
- **Language (1.10):** the conversation follows the tablet language (Polish or English).

## Screensaver

Choose a `weather` entity, a photo folder inside `/media` and up to 4 cameras in the options. Images are served through the integration view with a random key, so no HA token is stored on the tablet.

## Entities

| Type | Entities |
|---|---|
| Sensor | battery, light; diagnostic: battery temperature and health, Wi-Fi signal, free memory, uptime, last page load, WebView version, IP, app version, current URL, missing permissions; Aurora – conversation state, **Aurora – log** (last 30 events: wakes, rejections, announcements, watchdog) |
| Binary sensor | charging, motion, screen on, night time, night clock, fallback address, proximity |
| Switch | screen, auto brightness, night mode |
| Number | brightness (0-255) |
| Media player | sounds, `tts.speak` announcements, volume, stop |
| Button | reload dashboard, restart panel, stop sound, close popup, open settings on the tablet, quiet for an hour, apply settings, check for updates |
| Camera | tablet screenshot on demand |
| Update | app version from GitHub Releases, one-click install |
| Text | current panel URL |
| Notify | voice announcement (`notify.send_message`) |

## Services

| Service | Action |
|---|---|
| `hapanel.popup` | show a page or camera on top (`url`, `seconds`, `wake`, `title`) |
| `hapanel.say` | voice announcement (`message`, optional `volume`, `wake`) |
| `hapanel.converse` | Aurora announcement followed by an optional conversation (`message`, `person`, `listen`, `wait`, `volume`) |
| `hapanel.close_popup` | close the popup |
| `hapanel.export_settings` / `hapanel.import_settings` | settings backup (no PIN, tokens or webhook) |

Target: the tablet media player (e.g. `media_player.panel`).

## Tablet events (webhook)

Events are fired as `hapanel_event`: `motion`, `touch`, `low_battery`, `start`, `screen`, `wake_word`, `wake_reject`, `voice_start`, `voice_end`, `settings`, `watchdog`, `quiet`.

```yaml
triggers:
  - trigger: event
    event_type: hapanel_event
    event_data: { event: motion, state: true }
```

## Licence

Add a `LICENSE` file before public distribution.
