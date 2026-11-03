"""Aurora – rozmowa głosowa z tabletem HA Panel.

Tablet nagrywa wypowiedź (WAV 16 kHz) i wysyła ją do webhooka integracji. Tutaj:
rozpoznanie mowy (STT) → rozmowa (agent konwersacji, osobny dla dzieci i dorosłych) → synteza głosu (TTS).
Dodatkowo: rozpoznawanie rozmówcy, godziny dla dzieci, proste polecenia (światło, szum na sen, bajka na telefon),
pożegnania, gwiazdki, pamięć o domownikach i dziennik rozmów do podsumowań dla rodziców.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import struct
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AGENT_ADULT, CONF_AGENT_CHILD, CONF_AGENT_FALLBACK, CONF_AI_TASK, CONF_ASSISTANT_NAME, CONF_CHILD_FROM,
    CONF_CHILD_TO, CONF_CONTEXT, CONF_PERSONS, CONF_SLEEP_SOUND, CONF_SLEEP_SOUND_MIN, CONF_STT, CONF_STT_FALLBACK,
    CONF_TTS, CONF_TTS_FALLBACK, DEFAULT_ASSISTANT_NAME, DOMAIN, SIGNAL_AURORA, STORAGE_KEY, STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
FAREWELL = re.compile(
    r"\b(pa+|pa pa|papa|do widzenia|dobranoc|dobrej nocy|na razie|to wszystko|koniec rozmowy|wystarczy|"
    r"do zobaczenia|nara|cześć na razie)\b", re.I)
LIGHT_ON = re.compile(r"\b(włącz|wlacz|zapal|zaświeć|zaswiec)\w*\b.*\b(świat|swiat|lamp)", re.I)
LIGHT_OFF = re.compile(r"\b(wyłącz|wylacz|zgaś|zgas|zgaś)\w*\b.*\b(świat|swiat|lamp)", re.I)
SLEEP_SOUND = re.compile(r"\b(szum|kołysank|kolysank|muzyk\w* do (spania|snu)|deszcz|fale morza|odgłos)", re.I)
PHONE_STORY = re.compile(r"(bajk\w*.*telefon|telefon\w*.*bajk)", re.I)
STAR = re.compile(r"\b(masz|dostajesz|zdobywasz|zdobyłaś|zdobyłeś|należy ci się)\b[^.!?]{0,20}\bgwiazdk", re.I)
SESSION_IDLE = 90          # s bez tury = koniec sesji (zapis pamięci i dziennika)


def _now() -> datetime:
    return dt_util.now()


def _hm(s: str | None, default: str) -> tuple[int, int]:
    try:
        h, m = str(s or default).split(":")[:2]
        return int(h), int(m)
    except (ValueError, TypeError):
        h, m = default.split(":")
        return int(h), int(m)


def _pcm_from_wav(data: bytes) -> bytes:
    """Zwraca surowe PCM z pliku WAV (szuka bloku 'data'); jeśli to nie WAV – zwraca dane bez zmian."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data
    pos = 12
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if cid == b"data":
            return data[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)
    return data[44:]


NO_CONNECTION = "Przepraszam, nie mam teraz połączenia. Spróbujmy za chwilę."


def _overloaded(err: Exception) -> bool:
    """Chwilowe przeciążenie usługi (np. Google 503 / UNAVAILABLE / high demand)."""
    t = str(err).lower()
    return any(k in t for k in ("503", "unavailable", "overloaded", "high demand"))


class Aurora:
    """Wspólny „mózg” Aurory dla wszystkich tabletów."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {"memory": {}, "stars": {}, "log": []}
        self.sessions: dict[str, dict] = {}
        self.last_announce: dict[str, dict] = {}      # entry_id -> {text, person, at}
        self._unsub = None

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self.data.update({k: stored.get(k, v) for k, v in self.data.items()})
        self._unsub = async_track_time_interval(self.hass, self._sweep, timedelta(seconds=30))

    def unload(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 5)
        async_dispatcher_send(self.hass, SIGNAL_AURORA)

    # ------------------------------------------------------------------ osoby i kontekst
    def persons(self, options: dict) -> list[dict]:
        ent = options.get(CONF_PERSONS)
        st = self.hass.states.get(ent) if ent else None
        raw = st.attributes.get("osoby") if st else None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                raw = None
        return [p for p in (raw or []) if isinstance(p, dict) and p.get("id")]

    def person(self, options: dict, pid: str) -> dict | None:
        pid = (pid or "").lower()
        return next((p for p in self.persons(options) if str(p["id"]).lower() == pid), None)

    def match_person(self, options: dict, text: str) -> dict | None:
        low = f" {text.lower()} "
        for p in self.persons(options):
            names = [p.get("imie", "")] + list(p.get("aliasy") or [])
            for n in names:
                n = str(n).strip().lower()
                if n and re.search(rf"\b{re.escape(n)}\w{{0,3}}\b", low):
                    return p
        return None

    def context_text(self, options: dict) -> str:
        ent = options.get(CONF_CONTEXT)
        st = self.hass.states.get(ent) if ent else None
        if not st:
            return ""
        return str(st.attributes.get("tekst") or st.state or "")[:6000]

    def is_child(self, p: dict | None) -> bool:
        return p is None or str(p.get("rola", "dziecko")).lower().startswith("dzie")

    def child_hours_ok(self, options: dict) -> bool:
        f = _hm(options.get(CONF_CHILD_FROM), "06:30")
        t = _hm(options.get(CONF_CHILD_TO), "21:00")
        n = _now()
        cur = n.hour * 60 + n.minute
        a, b = f[0] * 60 + f[1], t[0] * 60 + t[1]
        return a <= cur < b if a <= b else (cur >= a or cur < b)

    def name(self, options: dict) -> str:
        return options.get(CONF_ASSISTANT_NAME) or DEFAULT_ASSISTANT_NAME

    def build_prompt(self, options: dict, p: dict | None, entry_id: str, source: str) -> str:
        n = _now()
        name = self.name(options)
        who = (f"{p.get('imie')} ({'dziecko' if self.is_child(p) else 'dorosły'}"
               f"{', ' + p['opis'] if p and p.get('opis') else ''})") if p else "nieznana osoba – traktuj jak dziecko"
        lines = [
            f"Jesteś {name} – domowa asystentka tej rodziny. Mówisz po polsku przez tablet w salonie.",
            "Twoje odpowiedzi są czytane na głos: zwykle 1–3 krótkie zdania, bez list, nagłówków, emoji, "
            "gwiazdek i skrótów. Godziny i liczby pisz tak, żeby dobrze brzmiały czytane (np. „o siódmej trzydzieści”).",
            f"Teraz jest {DNI[n.weekday()]}, {n.strftime('%d.%m.%Y')}, godzina {n.strftime('%H:%M')}.",
            f"Rozmawiasz z: {who}.",
            "Charakter: ciepła, rodzinna i cierpliwa; zabawna (żarty, zagadki, rymowanki); nauczycielska – pomagasz "
            "w nauce, ale nie podajesz gotowych odpowiedzi do zadań domowych, tylko naprowadzasz pytaniami; "
            "przy dorosłych konkretna i rzeczowa.",
            "Zabawy i nauka: quizy z tematów najbliższych sprawdzianów i kartkówek (są w informacjach o domu), "
            "zagadki dopasowane do wieku, nauka angielskiego (proste słówka i zdania), tabliczka mnożenia, "
            "dyktando (podaj słowo i poproś o przeliterowanie). Za dobrą odpowiedź w quizie lub zadaniu powiedz "
            "wprost „Masz gwiazdkę!”.",
            "Bajki: gdy ktoś prosi o bajkę, opowiedz spokojną, ciepłą bajkę na kilka minut (wyjątek od krótkich "
            "odpowiedzi) i zakończ łagodnie, zachęcając do snu.",
            "Gdy rozmówca się żegna, pożegnaj się krótko i dopasuj do pory dnia (rano: miłego dnia, wieczorem: dobranoc).",
        ]
        if self.is_child(p):
            lines += [
                "Zasady przy dzieciach: prosty język; nie podawaj haseł, kodów, numerów kart ani danych logowania; "
                "nie opisuj obrazu z kamer; nie steruj bramą, furtką, alarmem ani zamkami; nie zmieniaj limitów "
                "telefonu – możesz tylko powiedzieć, ile czasu ekranu zostało. Jeśli dziecko mówi o smutku, "
                "strachu, bólu albo o tym, że ktoś je krzywdzi – okaż troskę i zachęć, żeby powiedziało mamie "
                "lub tacie. Wieczorem zachęcaj do snu, a nie do dłuższej zabawy.",
            ]
        else:
            lines += [
                "Zasady przy dorosłych: możesz sterować domem, jeśli masz takie narzędzia. Bramy, furtki, pompy "
                "ciepła i ogrzewania nie uruchamiaj bezpośrednio – używaj skryptów z potwierdzeniem na telefonie, "
                "jeśli są dostępne, i powiedz, że czeka potwierdzenie.",
            ]
        facts = (self.data["memory"].get(str(p.get("id")).lower()) if p else None) or []
        if facts:
            lines.append(f"Co pamiętasz o {p.get('imie')}: " + "; ".join(facts[-40:]) + ".")
        if p:
            stars = self.data["stars"].get(str(p.get("id")).lower(), 0)
            if stars:
                lines.append(f"{p.get('imie')} ma już {stars} gwiazdek od ciebie.")
        ann = self.last_announce.get(entry_id)
        if source == "announce" and ann and (_now() - ann["at"]).total_seconds() < 180:
            lines.append(f"Przed chwilą powiedziałaś na głos: „{ann['text']}”. Rozmówca właśnie na to odpowiada.")
        ctx = self.context_text(options)
        if ctx:
            lines.append("Informacje o domu (używaj tylko, gdy pasują do pytania):\n" + ctx)
        return "\n".join(lines)

    # ------------------------------------------------------------------ silniki
    async def stt(self, options: dict, pcm: bytes) -> str:
        from homeassistant.components import stt

        for eid in (options.get(CONF_STT), options.get(CONF_STT_FALLBACK)):
            if not eid:
                continue
            try:
                prov = stt.async_get_speech_to_text_entity(self.hass, eid)
                if prov is None:
                    continue
                langs = list(getattr(prov, "supported_languages", []) or [])
                lang = next((l for l in langs if str(l).lower().startswith("pl")), langs[0] if langs else "pl")
                meta = stt.SpeechMetadata(
                    language=lang, format=stt.AudioFormats.WAV, codec=stt.AudioCodecs.PCM,
                    bit_rate=stt.AudioBitRates.BITRATE_16, sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                    channel=stt.AudioChannels.CHANNEL_MONO)

                async def stream():
                    for i in range(0, len(pcm), 4096):
                        yield pcm[i:i + 4096]

                fn = getattr(prov, "internal_async_process_audio_stream", None) or prov.async_process_audio_stream
                res = None
                for attempt in range(2):
                    try:
                        res = await asyncio.wait_for(fn(meta, stream()), timeout=25)
                        break
                    except Exception as err:  # noqa: BLE001
                        if attempt == 0 and _overloaded(err):
                            await asyncio.sleep(3)
                            continue
                        raise
                text = (getattr(res, "text", None) or "").strip()
                if text:
                    return text
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Aurora: rozpoznawanie mowy (%s) nie powiodło się: %s", eid, err)
        return ""

    async def tts_url(self, options: dict, text: str) -> str:
        from homeassistant.components import tts

        for eid in (options.get(CONF_TTS), options.get(CONF_TTS_FALLBACK)):
            if not eid or not text:
                continue
            try:
                lang = None
                try:
                    from homeassistant.components.tts.helper import get_engine_instance

                    ent = get_engine_instance(self.hass, eid)
                    langs = list(getattr(ent, "supported_languages", []) or [])
                    lang = next((l for l in langs if str(l).lower().startswith("pl")), None)
                except Exception:  # noqa: BLE001
                    lang = None
                media_id = tts.generate_media_source_id(self.hass, text, engine=eid, language=lang)
                play = await media_source.async_resolve_media(self.hass, media_id, None)
                return async_process_play_media_url(self.hass, play.url)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Aurora: synteza mowy (%s) nie powiodła się: %s", eid, err)
        return ""

    async def converse(self, options: dict, text: str, sess: dict, child: bool, prompt: str) -> tuple[str, bool]:
        from homeassistant.components import conversation

        agents = [options.get(CONF_AGENT_CHILD) if child else options.get(CONF_AGENT_ADULT),
                  options.get(CONF_AGENT_ADULT), options.get(CONF_AGENT_FALLBACK)]
        tried = set()
        for agent in agents:
            if agent in tried:
                continue
            tried.add(agent)
            try:
                kwargs = dict(text=text, conversation_id=sess.get("conv_id"), context=Context(),
                              language="pl", agent_id=agent)
                res = None
                for attempt in range(2):
                    try:
                        try:
                            res = await asyncio.wait_for(
                                conversation.async_converse(self.hass, extra_system_prompt=prompt, **kwargs), timeout=40)
                        except TypeError:   # starszy HA bez extra_system_prompt
                            res = await asyncio.wait_for(conversation.async_converse(self.hass, **kwargs), timeout=40)
                        break
                    except Exception as err:  # noqa: BLE001
                        if attempt == 0 and _overloaded(err):   # chwilowe przeciążenie serwera – jedna ponowna próba
                            await asyncio.sleep(3)
                            continue
                        raise
                speech = (res.response.speech or {}).get("plain", {}).get("speech", "").strip()
                if not speech:
                    continue
                if agent == agents[0]:
                    sess["conv_id"] = res.conversation_id
                return speech, bool(getattr(res, "continue_conversation", False))
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Aurora: agent %s nie odpowiedział: %s", agent, err)
        return NO_CONNECTION, False

    # ------------------------------------------------------------------ jedna tura rozmowy
    async def process(self, coordinator, entry, wav: bytes, session: str, person: str, source: str, turn: int) -> dict:
        options = dict(entry.options)
        sess = self.sessions.get(session)
        if sess is None:
            sess = {"entry_id": entry.entry_id, "person": person or "", "turns": [], "source": source,
                    "started": _now(), "conv_id": None, "asked_who": False, "stars": 0}
            self.sessions[session] = sess
        sess["last"] = _now()
        if person and not sess["person"]:
            sess["person"] = person

        heard = await self.stt(options, _pcm_from_wav(wav))
        if not heard:
            return {"reply": "", "audio": "", "continue": turn < 1, "end": turn >= 1, "heard": ""}
        sess["turns"].append(("user", heard))

        p = self.person(options, sess["person"]) if sess["person"] else None
        if p is None:
            p = self.match_person(options, heard)
            if p:
                sess["person"] = str(p["id"])
        reply = ""
        end = False
        dim = False
        cont = True

        if p is None and not sess["asked_who"] and self.persons(options) and source != "announce":
            sess["asked_who"] = True
            reply = "Cześć! Kto ze mną rozmawia?"
        else:
            child = self.is_child(p)
            farewell = bool(FAREWELL.search(heard))
            if child and not self.child_hours_ok(options):
                reply = "Już późno i pora spać. Porozmawiamy jutro. Dobranoc i kolorowych snów!"
                end, dim = True, True
            elif (r := await self._command(coordinator, options, p, heard, child)) is not None:
                reply, end, dim = r
            else:
                prompt = self.build_prompt(options, p, entry.entry_id, sess["source"])
                reply, _ = await self.converse(options, heard, sess, child, prompt)
                if reply == NO_CONNECTION and sess.get("source") in ("wake", "proximity"):
                    # wybudzenie słowem/gestem (często fałszywe) – przy awarii po cichu kończymy rozmowę
                    _LOGGER.info("Aurora: brak odpowiedzi agenta po wybudzeniu (%s) – kończę bez komunikatu", sess.get("source"))
                    return {"reply": "", "audio": "", "continue": False, "end": True, "heard": heard}
                if farewell:
                    end = True
                    dim = "dobranoc" in heard.lower() or _now().hour >= 20
                if child and p and STAR.search(reply):
                    pid = str(p["id"]).lower()
                    self.data["stars"][pid] = int(self.data["stars"].get(pid, 0)) + 1
                    sess["stars"] += 1
                    self._save()
        sess["turns"].append(("aurora", reply))
        audio = await self.tts_url(options, reply)
        if end:
            self.hass.async_create_task(self.finish(session))
            cont = False
        return {"heard": heard, "reply": reply, "audio": audio, "continue": cont, "end": end, "dim": dim,
                "person": sess["person"]}

    async def _command(self, coordinator, options: dict, p: dict | None, text: str, child: bool):
        """Proste polecenia obsługiwane bez AI. Zwraca (odpowiedź, koniec, przyciemnij) albo None."""
        light = (p or {}).get("swiatlo")
        if light and (LIGHT_ON.search(text) or LIGHT_OFF.search(text)):
            on = bool(LIGHT_ON.search(text)) and not LIGHT_OFF.search(text)
            try:
                await self.hass.services.async_call("light" if light.startswith("light.") else "homeassistant",
                                                    "turn_on" if on else "turn_off", {"entity_id": light}, blocking=True)
                return ("Już zapalam światło." if on else "Gaszę światło. Śpij dobrze!"), False, False
            except Exception:  # noqa: BLE001
                return "Nie udało mi się zmienić światła.", False, False
        if SLEEP_SOUND.search(text) and options.get(CONF_SLEEP_SOUND):
            minutes = int(options.get(CONF_SLEEP_SOUND_MIN) or 20)
            url = options[CONF_SLEEP_SOUND]

            async def _play():
                await asyncio.sleep(4)          # najpierw Aurora mówi, potem szum
                try:
                    await coordinator.api.call("/playsound", url=url)
                except Exception:  # noqa: BLE001
                    pass

            self.hass.async_create_task(_play())

            @callback
            def _stop(_now_):
                self.hass.async_create_task(coordinator.api.call("/stopsound"))

            async_call_later(self.hass, 4 + minutes * 60, _stop)
            return f"Włączam spokojny szum na {minutes} minut. Zamknij oczka. Dobranoc!", True, True
        if PHONE_STORY.search(text):
            if self.hass.services.has_service("script", "aurora_bajka_na_telefon"):
                self.hass.async_create_task(self.hass.services.async_call(
                    "script", "aurora_bajka_na_telefon",
                    {"variables": {"osoba": (p or {}).get("id", ""), "prosba": text}}, blocking=False))
                return "Już wymyślam bajkę i zaraz wyślę ją na twój telefon. Połóż się wygodnie.", True, True
            return None
        return None

    # ------------------------------------------------------------------ koniec sesji: pamięć i dziennik
    async def _sweep(self, _now_=None) -> None:
        cutoff = _now() - timedelta(seconds=SESSION_IDLE)
        for sid, s in list(self.sessions.items()):
            if s.get("last", s["started"]) < cutoff:
                await self.finish(sid)

    async def finish(self, session: str) -> None:
        s = self.sessions.pop(session, None)
        if not s or not s["turns"]:
            return
        entry = self.hass.config_entries.async_get_entry(s["entry_id"])
        options = dict(entry.options) if entry else {}
        pid = (s.get("person") or "").lower()
        p = self.person(options, pid) if pid else None
        convo = "\n".join(f"{'Aurora' if w == 'aurora' else (p or {}).get('imie', 'Rozmówca')}: {t}" for w, t in s["turns"])
        info = {"facts": [], "topics": [], "concern": False, "concern_text": ""}
        ai = options.get(CONF_AI_TASK)
        if ai and self.hass.services.has_service("ai_task", "generate_data"):
            known = "; ".join(self.data["memory"].get(pid, [])[-40:])
            instr = (
                "Przeanalizuj rozmowę domowej asystentki z członkiem rodziny i zwróć WYŁĄCZNIE JSON bez komentarzy:\n"
                '{"facts": ["nowe trwałe fakty o rozmówcy warte zapamiętania, np. ulubione zwierzę, kolor, bajka, '
                'imię zwierzaka, plany, zainteresowania – krótko, po polsku, bez powtarzania znanych"], '
                '"topics": ["2-4 krótkie tematy rozmowy"], "concern": false, '
                '"concern_text": "jeśli dziecko mówi o czymś niepokojącym (smutek, strach, ból, przemoc, krzywda) – '
                'krótki opis dla rodzica, inaczej pusty"}\n'
                f"Już znane fakty: {known or 'brak'}\n\nRozmowa:\n{convo[:8000]}")
            try:
                resp = await self.hass.services.async_call(
                    "ai_task", "generate_data",
                    {"task_name": "aurora_pamiec", "entity_id": ai, "instructions": instr},
                    blocking=True, return_response=True)
                raw = (resp or {}).get("data")
                if isinstance(raw, str):
                    m = re.search(r"\{.*\}", raw, re.S)
                    raw = json.loads(m.group(0)) if m else {}
                if isinstance(raw, dict):
                    info.update({k: raw.get(k, v) for k, v in info.items()})
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Aurora: analiza rozmowy nie powiodła się: %s", err)
        if pid and info["facts"]:
            mem = self.data["memory"].setdefault(pid, [])
            for f in info["facts"]:
                f = str(f).strip()
                if f and f not in mem:
                    mem.append(f[:200])
            del mem[:-80]
        entry_log = {
            "czas": s["started"].isoformat(timespec="minutes"),
            "osoba": (p or {}).get("imie") or pid or "nieznana",
            "rola": "dziecko" if self.is_child(p) else "dorosły",
            "zrodlo": s.get("source", ""),
            "tury": len([1 for w, _ in s["turns"] if w == "user"]),
            "tematy": [str(t)[:60] for t in (info["topics"] or [])][:4],
            "gwiazdki": s.get("stars", 0),
            "niepokoj": bool(info["concern"]),
            "niepokoj_opis": str(info.get("concern_text") or "")[:300],
        }
        log = self.data["log"]
        log.append(entry_log)
        limit = (_now() - timedelta(days=14)).isoformat()
        self.data["log"] = [e for e in log if e["czas"] >= limit][-500:]
        self._save()
        self.hass.bus.async_fire(f"{DOMAIN}_conversation_end", {**entry_log, "entry_id": s["entry_id"]})

    # ------------------------------------------------------------------ dla usług i czujników
    def today_log(self) -> list[dict]:
        d = _now().date().isoformat()
        return [e for e in self.data["log"] if e["czas"].startswith(d)]

    def forget(self, person: str, fact: str | None = None) -> None:
        pid = person.lower()
        if not fact:
            self.data["memory"].pop(pid, None)
        else:
            self.data["memory"][pid] = [f for f in self.data["memory"].get(pid, []) if fact.lower() not in f.lower()]
        self._save()

    def add_stars(self, person: str, count: int) -> None:
        pid = person.lower()
        self.data["stars"][pid] = max(0, int(self.data["stars"].get(pid, 0)) + int(count))
        self._save()
