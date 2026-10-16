"""Listen: stories and answers read aloud with Azure AI Speech neural voices.

Uses the Foundry account (an Azure AI Services resource, which includes Speech) with the app's managed
identity, so there are no keys: the REST API takes a Microsoft Entra token as
``Authorization: Bearer aad#<resource id>#<token>``. Audio is cached, so a story heard by many fans is
synthesized once. When Speech isn't configured (local runs), the endpoint reports that and the app uses
the phone's own voice instead.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import OrderedDict
# escape() makes text safe to put into SSML; no XML is ever parsed here.
from xml.sax.saxutils import escape  # nosec B406

import httpx

log = logging.getLogger("lasso.speech")

# One warm neural voice per language: US English, Spain Spanish, Brazilian Portuguese, French.
VOICES = {"en": ("en-US", "en-US-AndrewNeural"), "es": ("es-ES", "es-ES-AlvaroNeural"),
          "pt": ("pt-BR", "pt-BR-AntonioNeural"), "fr": ("fr-FR", "fr-FR-HenriNeural")}
SCOPE = "https://cognitiveservices.azure.com/.default"
CACHE_ITEMS = 300


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


_MIN = re.compile(r"(?:\b(at|in|aos|à|a)\s+)?\b(\d{1,3})(?:\s*\+\s*(\d{1,2}))?['’′]")
_VS = {"en": "versus", "es": "contra", "pt": "contra", "fr": "contre"}
_TO = {"en": "to", "es": "a", "pt": "a", "fr": "à"}
_PLUS = {"en": "plus", "es": "más", "pt": "mais", "fr": "plus"}
_WORDS = {"en": (("xG", "expected goals"), ("pts", "points")), "es": (("xG", "goles esperados"), ("pts", "puntos")),
          "pt": (("xG", "gols esperados"), ("pts", "pontos")), "fr": (("xG", "buts attendus"), ("pts", "points"))}


def spoken(text: str, lang: str) -> str:
    """Text as a voice should read it: written minutes (82') become words a voice says ("the 82nd minute"),
    "v" between teams becomes "versus", scores read "2 to 1", and abbreviations are spelled out."""
    lang = lang if lang in _VS else "en"

    def minute(m: re.Match) -> str:
        prep, n, extra = m.group(1), int(m.group(2)), m.group(3)
        plus = f" {_PLUS[lang]} {extra}" if extra else ""
        if lang == "en":
            return f"in the {_ordinal(n)} minute{plus}" if prep else f"{_ordinal(n)} minute{plus}"
        if lang == "pt":
            return f"aos {n}{plus} minutos" if prep == "aos" else f"minuto {n}{plus}"
        if lang == "fr":
            return f"à la {n}e minute{plus}" if prep == "à" else f"{n}e minute{plus}"
        return f"{prep + ' ' if prep else ''}minuto {n}{plus}"

    text = _MIN.sub(minute, text)
    text = re.sub(r"(?<=\w) v\.? (?=\w)", f" {_VS[lang]} ", text)
    text = re.sub(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b(?!\s*%)", lambda m: f"{m.group(1)} {_TO[lang]} {m.group(2)}", text)
    for short, full in _WORDS[lang]:
        text = re.sub(rf"\b{short}\b", full, text)
    return text.replace("→", f" {_TO[lang]} ")


class Speech:
    def __init__(self, region: str, resource_id: str, client_id: str = "", daily_limit: int = 1500):
        self.region, self.resource_id, self.client_id = region, resource_id, client_id
        self.daily_limit = daily_limit
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._token: tuple[str, float] | None = None
        self._cred = None
        self._http: httpx.AsyncClient | None = None
        self._day, self._count = "", 0

    @property
    def enabled(self) -> bool:
        return bool(self.region and self.resource_id)

    async def _bearer(self) -> str:
        if self._token and self._token[1] - time.time() > 120:
            return self._token[0]
        if self._cred is None:
            from azure.identity.aio import DefaultAzureCredential

            self._cred = DefaultAzureCredential(managed_identity_client_id=self.client_id or None)
        tok = await self._cred.get_token(SCOPE)
        value = f"aad#{self.resource_id}#{tok.token}"
        self._token = (value, float(tok.expires_on))
        return value

    def _allowed(self) -> bool:
        day = time.strftime("%Y-%m-%d")
        if day != self._day:
            self._day, self._count = day, 0
        if self._count >= self.daily_limit:
            return False
        self._count += 1
        return True

    async def synthesize(self, text: str, lang: str) -> bytes | None:
        """MP3 audio for the text in the fan's language, or None if Speech is off, capped or failing."""
        if not self.enabled or not text.strip():
            return None
        xml_lang, voice = VOICES.get(lang, VOICES["en"])
        text = spoken(text, lang)
        key = hashlib.sha1(f"{voice}|{text}".encode(), usedforsecurity=False).hexdigest()  # a cache key only
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        if not self._allowed():
            log.warning("speech daily limit reached")
            return None
        ssml = (f"<speak version='1.0' xml:lang='{xml_lang}'><voice name='{voice}'>"
                f"<prosody rate='-4%'>{escape(text)}</prosody></voice></speak>")
        try:
            if self._http is None:
                self._http = httpx.AsyncClient(timeout=15)
            r = await self._http.post(
                f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1",
                content=ssml.encode("utf-8"),
                headers={"Authorization": f"Bearer {await self._bearer()}",
                         "Content-Type": "application/ssml+xml",
                         "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3", "User-Agent": "lasso"})
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("speech synthesis failed: %r", e)
            return None
        self._cache[key] = r.content
        while len(self._cache) > CACHE_ITEMS:
            self._cache.popitem(last=False)
        return r.content
