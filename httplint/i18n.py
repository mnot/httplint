import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta
from typing import Any, Dict, Generator, Optional, Tuple

from babel import Locale, UnknownLocaleError
from babel.dates import format_timedelta as babel_format_timedelta
from babel.support import NullTranslations, Translations

_LOCALEDIR = os.path.join(os.path.dirname(__file__), "translations")
_translations_cache: Dict[str, NullTranslations] = {}
_locale_var: ContextVar[str] = ContextVar("locale", default="en")
# The message catalog behind the active locale ("" if there isn't one).
_catalog_var: ContextVar[str] = ContextVar("catalog", default="")


def _resolve_locale(locale_name: Optional[str]) -> Tuple[str, str]:
    """
    Return the locale to use (locale_name if Babel recognises it, otherwise "en"),
    and the name of the message catalog that serves it ("" if there isn't one).
    """
    if not locale_name:
        return "en", ""
    try:
        language = Locale.parse(locale_name).language
    except (ValueError, UnknownLocaleError):
        return "en", ""
    if os.path.isdir(os.path.join(_LOCALEDIR, language, "LC_MESSAGES")):
        return locale_name, language
    return locale_name, ""


@contextmanager
def set_locale(locale_name: Optional[str]) -> Generator[None, None, None]:
    """
    Set the locale for the application context. An unrecognised locale falls back to "en".
    """
    locale, catalog = _resolve_locale(locale_name)
    token = _locale_var.set(locale)
    catalog_token = _catalog_var.set(catalog)
    try:
        yield
    finally:
        _catalog_var.reset(catalog_token)
        _locale_var.reset(token)


def get_locale() -> str:
    """
    Return the currently active locale.
    """
    return _locale_var.get()


def get_translations() -> Optional[NullTranslations]:
    # Keyed by catalog, so the cache holds at most one entry per shipped translation.
    catalog = _catalog_var.get()
    if catalog not in _translations_cache:
        if catalog:
            _translations_cache[catalog] = Translations.load(_LOCALEDIR, [catalog])
        else:
            _translations_cache[catalog] = NullTranslations()
    return _translations_cache[catalog]


def translate(message: str) -> str:
    """
    Translate a message.
    """
    translations = get_translations()
    if translations:
        return translations.gettext(message)
    return message


def ngettext(singular: str, plural: str, count: int) -> str:
    """
    Translate a message with pluralization.
    """
    translations = get_translations()
    if translations:
        return translations.ngettext(singular, plural, count)
    return singular if count == 1 else plural


def format_timedelta(delta: timedelta | int, **kwargs: Any) -> str:
    """
    Format a timedelta object.
    """
    locale = _locale_var.get()
    return babel_format_timedelta(delta, locale=locale, **kwargs)


def L_(message: str) -> str:  # pylint: disable=invalid-name
    """
    Lazy marker for string extraction.
    """
    return message
