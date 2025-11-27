import os
from typing import Optional
from babel.support import Translations

_translations: Optional[Translations] = None


def set_locale(locale_name: str) -> None:
    """
    Set the locale for the application.
    """
    global _translations
    # We assume translations are in 'httplint/translations' (or similar)
    # For now, let's look in the package directory

    localedir = os.path.join(os.path.dirname(__file__), "translations")
    _translations = Translations.load(localedir, [locale_name])


def translate(message: str) -> str:
    """
    Translate a message.
    """
    if _translations:
        return _translations.gettext(message)
    return message


def ngettext(singular: str, plural: str, n: int) -> str:
    """
    Translate a message with pluralization.
    """
    if _translations:
        return _translations.ngettext(singular, plural, n)
    return singular if n == 1 else plural


def L_(message: str) -> str:
    """
    Lazy marker for string extraction.
    """
    return message
