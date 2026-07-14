"""Asynchronous translation service with bounded concurrency, cache limits,
safe transient retries, circuit breaking, structured logging, and fallbacks.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LANGUAGE_TARGETS = {'English': 'en', 'Telugu': 'te', 'Hindi': 'hi', 'Tamil': 'ta', 'Kannada': 'kn', 'Odia': 'or'}

FORCED_TRANSLATIONS = {'Telugu': {'You': 'మీరు',
            'Current Location': 'ప్రస్తుత స్థానం',
            'Bus details': 'బస్ వివరాలు',
            'Walking details': 'నడక వివరాలు',
            'Bike Auto Cab details': 'బైక్ ఆటో క్యాబ్ వివరాలు',
            'APSRTC Bus Details': 'APSRTC బస్సు వివరాలు',
            'Walking Details': 'నడక వివరాలు',
            'Bike / Auto / Cab Details': 'బైక్ / ఆటో / క్యాబ్ వివరాలు',
            'Ramakrishna Beach': 'రామకృష్ణ బీచ్',
            'RK Beach': 'ఆర్\u200cకే బీచ్',
            'Rushikonda Beach': 'రుషికొండ బీచ్',
            'Yarada Beach': 'యారాడ బీచ్',
            'Bheemunipatnam Beach': 'భీమునిపట్నం బీచ్',
            "Lawson's Bay Beach": 'లాసన్స్ బే బీచ్',
            'Sagar Nagar Beach': 'సాగర్ నగర్ బీచ్',
            'Gangavaram Beach': 'గంగవరం బీచ్',
            'Appikonda Beach': 'అప్పికొండ బీచ్',
            'Mangamaripeta Beach': 'మంగమారిపేట బీచ్',
            'Jodugullapalem Beach': 'జోడుగుళ్లపాలెం బీచ్',
            'Mutyalammapalem Beach': 'ముత్యాలమ్మపాలెం బీచ్',
            'Pudimadaka Beach': 'పుడిమడక బీచ్',
            'Divis Beach': 'దివిస్ బీచ్',
            'Kapuluppada Beach': 'కాపులుప్పాడ బీచ్',
            'Visakhapatnam': 'విశాఖపట్నం',
            'Vizag': 'వైజాగ్',
            'Bheemunipatnam': 'భీమునిపట్నం',
            'Mutyalammapalem': 'ముత్యాలమ్మపాలెం',
            'Kapuluppada': 'కాపులుప్పాడ',
            'Kommadi': 'కొమ్మడి',
            'Gajuwaka': 'గాజువాక',
            'Jagadamba': 'జగదాంబ',
            'Railway Station': 'రైల్వే స్టేషన్',
            'Fishing Beach': 'ఫిషింగ్ బీచ్',
            'Coastal Village': 'తీర గ్రామం',
            'Historic Beach': 'చారిత్రక బీచ్',
            'Tourist Beach': 'పర్యాటక బీచ్',
            'Family Beach': 'కుటుంబ బీచ్',
            'Urban Beach': 'నగర బీచ్',
            'Scenic Beach': 'సుందరమైన బీచ్',
            'Local Beach': 'స్థానిక బీచ్',
            'Water Sports Beach': 'వాటర్ స్పోర్ట్స్ బీచ్',
            'Located at': 'ఉన్న ప్రదేశం',
            'is famous for': 'కు ప్రసిద్ధి',
            'Here are popular beaches in Vizag 😊': 'వైజాగ్\u200cలోని ప్రసిద్ధ బీచ్\u200cలు ఇక్కడ ఉన్నాయి 😊',
            'Here are popular beaches in Vizag': 'వైజాగ్\u200cలోని ప్రసిద్ధ బీచ్\u200cలు ఇక్కడ ఉన్నాయి',
            'Beach Road': 'బీచ్ రోడ్',
            'Rushikonda Road': 'రుషికొండ రోడ్',
            'Yarada Village': 'యారాడ గ్రామం',
            'Pedda Waltair': 'పెద్ద వాల్టెయిర్',
            'Sagar Nagar': 'సాగర్ నగర్',
            'Gangavaram': 'గంగవరం',
            'Appikonda': 'అప్పికొండ',
            'Mangamaripeta': 'మంగమారిపేట',
            'Jodugullapalem': 'జోడుగుళ్లపాలెం',
            'Pudimadaka': 'పుడిమడక',
            'Anakapalle': 'అనకాపల్లి',
            'Near Divis Laboratories': 'దివిస్ ల్యాబొరేటరీస్ సమీపంలో',
            'Calm Beach': 'ప్రశాంతమైన బీచ్',
            'Photography Spot': 'ఫోటోగ్రఫీ ప్రదేశం',
            'Photography Beach': 'ఫోటోగ్రఫీ బీచ్',
            'Village Beach': 'గ్రామీణ బీచ్',
            'Temple Beach': 'దేవాలయ బీచ్',
            'Coastal Area': 'తీర ప్రాంతం',
            'Industrial Coastal Beach': 'పారిశ్రామిక తీర బీచ్',
            'Hidden Beach': 'దాగి ఉన్న బీచ్',
            'Cloudy': 'మేఘావృతం',
            'Thunderstorm': 'ఉరుములతో కూడిన వర్షం',
            'Partly sunny': 'పాక్షికంగా ఎండగా ఉంది',
            'Restaurant': 'రెస్టారెంట్',
            'Restaurants': 'రెస్టారెంట్లు',
            'Family restaurant': 'కుటుంబ రెస్టారెంట్',
            'Biryani restaurant': 'బిర్యానీ రెస్టారెంట్',
            'Chinese restaurant': 'చైనీస్ రెస్టారెంట్',
            'Fast food restaurant': 'ఫాస్ట్ ఫుడ్ రెస్టారెంట్',
            'Indian restaurant': 'ఇండియన్ రెస్టారెంట్',
            'Lunch restaurant': 'లంచ్ రెస్టారెంట్',
            'Non vegetarian restaurant': 'నాన్ వెజిటేరియన్ రెస్టారెంట్',
            'South Indian restaurant': 'సౌత్ ఇండియన్ రెస్టారెంట్',
            'Vegetarian restaurant': 'వెజిటేరియన్ రెస్టారెంట్'}}

SKIP_TRANSLATE_KEYS = {'image', 'url', 'google_maps_url', 'image_url', 'website', 'URL', 'map_url', 'rapido_app', 'googleMapsUrl'}

_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
_TRANSIENT_STATUSES = {429, 502, 503, 504}
_MAX_CACHE_ENTRIES = 1000
_CACHE_TTL_SECONDS = 1800
_TRANSLATION_CONCURRENCY = 4
_MAX_ATTEMPTS = 3

_cache: "OrderedDict[tuple[str, str, str], tuple[float, str]]" = OrderedDict()
_cache_lock = asyncio.Lock()
_translation_semaphore = asyncio.Semaphore(_TRANSLATION_CONCURRENCY)


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    consecutive_failures: int = 0
    opened_at: float | None = None

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.cooldown_seconds:
            self.opened_at = None
            self.consecutive_failures = 0
            return False
        return True

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


_translation_breaker = CircuitBreaker()


def normalize_language(language: str = "English") -> str:
    value = str(language or "English").strip()
    return value if value in LANGUAGE_TARGETS else "English"


def apply_forced_translations(text: str, language: str) -> str:
    language = normalize_language(language)
    value = "" if text is None else str(text)
    if language == "English" or not value:
        return value

    replacements = FORCED_TRANSLATIONS.get(language, {})
    for source_text in sorted(replacements, key=len, reverse=True):
        value = value.replace(source_text, replacements[source_text])
    return value


def is_plain_non_language_value(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text.startswith(("http://", "https://")):
        return True
    if re.fullmatch(r"[₹0-9.,:;\-–—/()\s]+", text):
        return True
    if re.fullmatch(r"(?=.*\d)[A-Za-z0-9]{1,10}", text):
        return True
    return False


async def _cache_get(key: tuple[str, str, str]) -> str | None:
    now = time.monotonic()
    async with _cache_lock:
        item = _cache.get(key)
        if item is None:
            return None
        created_at, value = item
        if now - created_at > _CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return value


async def _cache_set(key: tuple[str, str, str], value: str) -> None:
    async with _cache_lock:
        _cache[key] = (time.monotonic(), value)
        _cache.move_to_end(key)
        while len(_cache) > _MAX_CACHE_ENTRIES:
            _cache.popitem(last=False)


def _translation_timeout() -> httpx.Timeout:
    return httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=3.0)


async def _translate_chunk(chunk: str, source: str, target: str) -> str:
    if _translation_breaker.is_open():
        raise RuntimeError("translation circuit is open")

    params = {
        "client": "gtx",
        "sl": source,
        "tl": target,
        "dt": "t",
        "q": chunk,
    }

    async with _translation_semaphore:
        async with httpx.AsyncClient(timeout=_translation_timeout()) as client:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    response = await client.get(_TRANSLATE_URL, params=params)

                    if response.status_code in _TRANSIENT_STATUSES:
                        if attempt < _MAX_ATTEMPTS:
                            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                            continue
                        response.raise_for_status()

                    response.raise_for_status()
                    data = response.json()
                    translated = "".join(
                        item[0]
                        for item in data[0]
                        if item and item[0]
                    ).strip()
                    _translation_breaker.record_success()
                    return translated or chunk

                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt < _MAX_ATTEMPTS:
                        await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                    _translation_breaker.record_failure()
                    logger.warning(
                        "Translation network failure",
                        extra={
                            "attempt": attempt,
                            "target_language": target,
                            "error_type": type(exc).__name__,
                        },
                    )
                    raise

                except httpx.HTTPStatusError as exc:
                    _translation_breaker.record_failure()
                    logger.warning(
                        "Translation HTTP failure",
                        extra={
                            "attempt": attempt,
                            "target_language": target,
                            "status_code": exc.response.status_code,
                        },
                    )
                    raise

                except (ValueError, KeyError, TypeError) as exc:
                    _translation_breaker.record_failure()
                    logger.warning(
                        "Translation response parsing failure",
                        extra={
                            "target_language": target,
                            "error_type": type(exc).__name__,
                        },
                    )
                    raise

    return chunk


async def translate_text_backend(
    text: str,
    language: str = "English",
    source: str = "auto",
) -> str:
    language = normalize_language(language)
    text = "" if text is None else str(text)

    if language == "English" or not text.strip():
        return text
    if is_plain_non_language_value(text):
        return text

    exact = FORCED_TRANSLATIONS.get(language, {}).get(text)
    if exact:
        return exact

    target = LANGUAGE_TARGETS[language]
    cache_key = (source, target, text)
    cached = await _cache_get(cache_key)
    if cached is not None:
        return cached

    if _translation_breaker.is_open():
        return apply_forced_translations(text, language)

    try:
        parts = re.findall(r".{1,420}(?:\s|$)", text, flags=re.S) or [text]
        chunks = [part.strip() for part in parts if part.strip()]
        translated_parts = await asyncio.gather(
            *(_translate_chunk(chunk, source, target) for chunk in chunks)
        )
        translated = " ".join(translated_parts).strip() or text
        translated = apply_forced_translations(translated, language)

        if language != "English" and re.search(r"[A-Za-z]{3,}", translated):
            fallback = apply_forced_translations(text, language)
            if len(re.findall(r"[A-Za-z]{3,}", fallback)) < len(
                re.findall(r"[A-Za-z]{3,}", translated)
            ):
                translated = fallback

        await _cache_set(cache_key, translated)
        return translated
    except Exception as exc:
        logger.warning(
            "Translation fallback used",
            extra={
                "target_language": target,
                "error_type": type(exc).__name__,
            },
        )
        return apply_forced_translations(text, language)


async def translate_to_english_backend(text: str) -> str:
    raw = "" if text is None else str(text).strip()
    if not raw:
        return raw

    indian_scripts = r"[\u0C00-\u0C7F\u0900-\u097F\u0B80-\u0BFF\u0C80-\u0CFF\u0B00-\u0B7F]"
    if re.search(r"[A-Za-z]", raw) and not re.search(indian_scripts, raw):
        return raw

    cache_key = ("auto", "en", raw)
    cached = await _cache_get(cache_key)
    if cached is not None:
        return cached

    if _translation_breaker.is_open():
        return raw

    try:
        translated = await _translate_chunk(raw, "auto", "en")
        translated = translated.strip() or raw
        await _cache_set(cache_key, translated)
        return translated
    except Exception as exc:
        logger.warning(
            "Query translation fallback used",
            extra={"error_type": type(exc).__name__},
        )
        return raw


async def localize_only_plain_messages(result: Any, language: str = "English") -> Any:
    language = normalize_language(language)
    if language == "English" or not isinstance(result, dict):
        return result

    recommendations = result.get("recommendations")
    if not isinstance(recommendations, list):
        return result

    localized = []
    for item in recommendations:
        if isinstance(item, dict) and set(item.keys()) == {"message"}:
            localized.append({
                "message": await translate_text_backend(
                    item.get("message", ""),
                    language,
                )
            })
        else:
            localized.append(item)

    output = dict(result)
    output["recommendations"] = localized
    output["language"] = language
    return output


async def translate_payload_backend(
    payload: Any,
    language: str = "English",
    key_name: str = "",
) -> Any:
    language = normalize_language(language)
    if language == "English":
        return payload

    if isinstance(payload, list):
        return await asyncio.gather(
            *(translate_payload_backend(item, language, key_name) for item in payload)
        )

    if isinstance(payload, dict):
        output = {}
        translatable = []
        keys = []
        for key, value in payload.items():
            if key in SKIP_TRANSLATE_KEYS:
                output[key] = value
            else:
                keys.append(key)
                translatable.append(
                    translate_payload_backend(value, language, key)
                )
        values = await asyncio.gather(*translatable) if translatable else []
        for key, value in zip(keys, values):
            output[key] = value
        return output

    if isinstance(payload, str):
        return await translate_text_backend(payload, language)

    return payload


async def localize_response(payload: Any, language: str = "English") -> Any:
    language = normalize_language(language)
    localized = await translate_payload_backend(payload, language)
    if isinstance(localized, dict):
        localized["language"] = language
    return localized