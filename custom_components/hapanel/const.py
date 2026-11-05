DOMAIN = "hapanel"
CONF_TOKEN = "api_token"
DEFAULT_PORT = 8765

# opcje (ustawienia wypychane na tablet)
CONF_DASHBOARD = "dashboard_url"
CONF_HOME_AFTER = "home_after"
CONF_SLEEP_AFTER = "sleep_after"
CONF_MOTION = "motion"
CONF_MOTION_THRESHOLD = "motion_threshold"
CONF_WAKE_ON_MOTION = "wake_on_motion"
CONF_AUTO_BRIGHT = "auto_brightness"
CONF_LOCK_TASK = "lock_task"
CONF_WAKE_ON_PROX = "wake_on_proximity"

CONF_NIGHT_ENABLED = "night_enabled"
CONF_NIGHT_START = "night_start"
CONF_NIGHT_END = "night_end"
CONF_NIGHT_BRIGHTNESS = "night_brightness"
CONF_NIGHT_WAKE = "night_wake"
CONF_FALLBACK = "fallback_urls"
CONF_PIN = "pin"          # tylko do zapisu: nigdy nie jest przechowywany w HA
CONF_CODE = "pair_code"

CONF_INJECT_CSS = "inject_css"
CONF_INJECT_JS = "inject_js"
CONF_ZOOM = "zoom"
# tylko po stronie HA: co pokazać na zegarze nocnym (encje)
CONF_TEMP_OUT = "temp_out"
CONF_TEMP_IN = "temp_in"
CONF_CLOCK_INFO = "clock_info"
CONF_WEBHOOK_ID = "webhook_id"          # w danych wpisu (nie w opcjach)
DEFAULT_APP_REPO = "bobby6robert/hapanel-app"

# --- Aurora: rozmowa głosowa (1.6, wymaga aplikacji 2.7) ---
# ustawienia wypychane na tablet
CONF_VOICE = "voice_enabled"
CONF_TALK_BUTTON = "talk_button"
CONF_WAKE_WORD = "wake_word"
CONF_WAKE_WORD_TEXT = "wake_word_text"
CONF_WAKE_QUIET_START = "wake_quiet_start"
CONF_WAKE_QUIET_END = "wake_quiet_end"
CONF_WAKE_PRESENCE = "wake_presence_only"
CONF_HOME_WORD = "home_word"
CONF_HOME_WORD_TEXT = "home_word_text"
CONF_PROXIMITY_TALK = "proximity_talk"
CONF_LISTEN_WAIT = "listen_wait"
CONF_SILENCE_MS = "silence_ms"
# ustawienia tylko po stronie HA
CONF_STT = "stt_entity"
CONF_STT_FALLBACK = "stt_fallback"
CONF_TTS = "tts_entity"
CONF_TTS_FALLBACK = "tts_fallback"
CONF_AGENT_ADULT = "agent_adult"
CONF_AGENT_CHILD = "agent_child"
CONF_AGENT_FALLBACK = "agent_fallback"
CONF_AI_TASK = "ai_task_entity"
CONF_PERSONS = "persons_entity"
CONF_CONTEXT = "context_entity"
CONF_CHILD_FROM = "child_from"
CONF_CHILD_TO = "child_to"
CONF_SLEEP_SOUND = "sleep_sound_url"
CONF_SLEEP_SOUND_MIN = "sleep_sound_minutes"
CONF_ASSISTANT_NAME = "assistant_name"
CONF_AUTO_UPDATE = "auto_update"

DEFAULT_ASSISTANT_NAME = "Aurora"
STORAGE_KEY = "hapanel_aurora"
STORAGE_VERSION = 1
SIGNAL_AURORA = "hapanel_aurora_updated"
