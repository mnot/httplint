import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta
from typing import Optional, Generator, Dict, Any
from babel.support import Translations, NullTranslations
from babel.dates import format_timedelta as babel_format_timedelta

_translations_cache: Dict[str, NullTranslations] = {}
_locale_var: ContextVar[str] = ContextVar("locale", default="en")


@contextmanager
def set_locale(locale_name: Optional[str]) -> Generator[None, None, None]:
    """
    Set the locale for the application context.
    """
    token = _locale_var.set(locale_name or "en")
    try:
        yield
    finally:
        _locale_var.reset(token)


def get_translations() -> Optional[NullTranslations]:
    locale = _locale_var.get()
    if locale not in _translations_cache:
        localedir = os.path.join(os.path.dirname(__file__), "translations")
        _translations_cache[locale] = Translations.load(localedir, [locale])
    return _translations_cache[locale]


def translate(message: str) -> str:
    """
    Translate a message.
    """
    t = get_translations()
    if t:
        return t.gettext(message)
    return message


def ngettext(singular: str, plural: str, n: int) -> str:
    """
    Translate a message with pluralization.
    """
    t = get_translations()
    if t:
        return t.ngettext(singular, plural, n)
    return singular if n == 1 else plural


def format_timedelta(delta: timedelta | int, **kwargs: Any) -> str:
    """
    Format a timedelta object.
    """
    locale = _locale_var.get()
    return babel_format_timedelta(delta, locale=locale, **kwargs)


def L_(message: str) -> str:
    """
    Lazy marker for string extraction.
    """
    return message
