import codecs
from typing import Optional

import chardet

from httplint.note import Note, categories, levels
from httplint.types import LinterProtocol

# Confidence threshold below which chardet results are ignored. chardet
# is conservative on Cyrillic/CJK (often 0.5–0.7) but the secondary
# _encodings_compatible check below filters out cases where the
# different name still decodes to the same text.
CHARDET_CONFIDENCE_THRESHOLD = 0.5


def _requires_utf8(media_type: str) -> bool:
    """
    True for media types whose definition mandates UTF-8. RFC 8259 requires
    UTF-8 for all JSON texts; by IANA convention this applies to any
    `+json` structured-syntax-suffix type as well.
    """
    if media_type in ("application/json", "text/json"):
        return True
    subtype = media_type.split("/", 1)[-1]
    return subtype.endswith("+json")


def _canonical(name: str) -> Optional[str]:
    try:
        return codecs.lookup(name).name
    except (LookupError, TypeError):
        return None


def verify_charset(linter: LinterProtocol) -> None:  # pylint: disable=too-many-return-statements
    """
    Verify that the content's character encoding matches what was declared
    (or implied) by the Content-Type header.
    """
    if not linter.content_hash or not linter.content_sample:
        return

    status_code = getattr(linter, "status_code", None)
    if status_code in [204, 205, 304, 206] + list(range(100, 199)) or getattr(
        linter, "is_head_response", False
    ):
        return

    if "content-type" not in linter.headers.parsed:
        return
    declared_type = linter.headers.parsed["content-type"][0]
    params = linter.headers.parsed["content-type"][1]
    if not declared_type:
        return

    declared_charset_raw = params.get("charset")
    if _requires_utf8(declared_type):
        # JSON et al. are always UTF-8 per RFC 8259; any charset parameter
        # is ignored by recipients.
        effective_charset_raw = "utf-8"
        is_implicit = declared_charset_raw is None
    elif declared_type.startswith("text/") and declared_charset_raw:
        effective_charset_raw = declared_charset_raw
        is_implicit = False
    else:
        # No declared or implied charset; nothing to check against.
        return

    declared_canonical = _canonical(effective_charset_raw)
    if declared_canonical is None:
        # Unknown declared encoding; another check reports this.
        return

    sample = linter.content_sample
    if not sample.strip():
        return

    # Pure-ASCII content is compatible with every ASCII-superset encoding;
    # don't second-guess it.
    if not any(b & 0x80 for b in sample):
        return

    # Primary check: does the declared encoding actually decode the content?
    try:
        sample.decode(effective_charset_raw, errors="strict")
        decodes = True
    except (UnicodeDecodeError, LookupError):
        decodes = False

    detection = chardet.detect(sample)
    detected_raw = detection.get("encoding")
    confidence = detection.get("confidence") or 0.0
    detected_canonical = _canonical(detected_raw) if detected_raw else None

    if not decodes:
        linter.notes.add(
            "content-type",
            CHARSET_UNDECODABLE,
            declared_charset=effective_charset_raw,
            detected_charset=detected_raw or "unknown",
        )
        return

    if (
        detected_canonical
        and detected_canonical != declared_canonical
        and confidence >= CHARDET_CONFIDENCE_THRESHOLD
        and not _encodings_compatible(declared_canonical, detected_canonical, sample)
    ):
        if is_implicit:
            linter.notes.add(
                "content-type",
                CHARSET_IMPLICIT_MISMATCH,
                media_type=declared_type,
                declared_charset=effective_charset_raw,
                detected_charset=detected_raw,
            )
        else:
            linter.notes.add(
                "content-type",
                CHARSET_MISMATCH,
                declared_charset=effective_charset_raw,
                detected_charset=detected_raw,
            )


def _encodings_compatible(declared: str, detected: str, sample: bytes) -> bool:
    """
    Return True if decoding `sample` with `declared` and with `detected`
    yields the same text. This catches cases where chardet picks a
    different name (e.g. windows-1252 vs iso-8859-1) for content that is
    identical under both.
    """
    try:
        a = sample.decode(declared, errors="strict")
        b = sample.decode(detected, errors="strict")
    except (UnicodeDecodeError, LookupError):
        return False
    return a == b


class CHARSET_MISMATCH(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The declared character encoding doesn't match the content."
    _text = """\
The `Content-Type` header declares the character encoding as `%(declared_charset)s`,
but the content appears to be encoded as `%(detected_charset)s`.

Recipients that trust the declared charset might misinterpret the content."""


class CHARSET_IMPLICIT_MISMATCH(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The content isn't %(declared_charset)s, as required for %(media_type)s."
    _text = """\
The `%(media_type)s` media type requires content to be encoded as
`%(declared_charset)s`, but the content appears to be `%(detected_charset)s`.

Recipients might interpret this content as `%(declared_charset)s` regardless
of what was sent, so non-ASCII characters may be misrendered."""


class CHARSET_UNDECODABLE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The content can't be decoded using the declared character encoding."
    _text = """\
The content was declared as `%(declared_charset)s` (either explicitly or by
the media type's definition), but it cannot be decoded using that encoding;
it looks more like `%(detected_charset)s`.

This will likely cause decoding errors in recipients."""
