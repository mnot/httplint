import codecs
from typing import Optional

import chardet

from httplint.content_encoding import BAD_BROTLI, BAD_GZIP, BAD_ZLIB
from httplint.note import Note, categories, levels
from httplint.types import LinterProtocol

# Confidence threshold below which chardet results are ignored. chardet
# is conservative on Cyrillic/CJK (often 0.5–0.7) but the secondary
# _encodings_compatible check below filters out cases where the
# different name still decodes to the same text.
CHARDET_CONFIDENCE_THRESHOLD = 0.5

# content_sample can fall short of "the end of the content" for three
# reasons: it hit content_sample_size's fixed byte cap, the message
# itself wasn't fully received, or content-encoding decoding aborted
# partway through. In each case a multi-byte character may be split at
# the cutoff point, so charset checks need to tolerate that rather than
# reporting genuinely valid content as undecodable.
_DECODE_FAILURE_NOTES = (BAD_GZIP, BAD_ZLIB, BAD_BROTLI)

# Bytes trimmed from the end of a truncated content_sample before the
# declared-vs-detected comparison runs, so a multi-byte character split
# by the cutoff can't make the two decodes diverge only because of where
# the cut landed. Comfortably covers UTF-8/UTF-16/UTF-32 (max 4
# bytes/character) and legacy multi-byte encodings, with margin to
# spare -- content_sample is already a bounded, best-effort sample, so
# trimming a few more bytes off it costs nothing.
TRUNCATION_SAFETY_MARGIN = 8


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


def _sample_is_truncated(linter: LinterProtocol) -> bool:
    """
    True if `content_sample` may not represent the actual end of the
    content: it hit the fixed byte cap, the message wasn't fully
    received, or content-encoding decoding stopped early after an error.
    """
    if linter.content_sample_truncated or not linter.complete:
        return True
    return any(isinstance(note, _DECODE_FAILURE_NOTES) for note in linter.notes)


def _decode_declared(sample: bytes, encoding: str, truncated: bool) -> Optional[str]:
    """
    Decode `sample` as `encoding` for the primary "does this decode at
    all" check. A genuinely invalid or non-text encoding name (e.g.
    "hex", "rot13") always fails here via LookupError before any
    incremental decoding is attempted, so it can never reach
    `codecs.getincrementaldecoder`, which has no such guard and would
    otherwise raise a codec-specific exception instead of a catchable
    one. If `truncated`, a trailing incomplete multi-byte sequence is
    tolerated -- of any length, since a message cut short by a dropped
    connection may leave a sample far smaller than
    TRUNCATION_SAFETY_MARGIN. Returns the decoded text, or None if
    decoding fails.
    """
    try:
        return sample.decode(encoding, errors="strict")
    except LookupError:
        return None
    except UnicodeDecodeError:
        if not truncated:
            return None
        try:
            return codecs.getincrementaldecoder(encoding)().decode(sample, final=False)
        except UnicodeDecodeError:
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
    truncated = _sample_is_truncated(linter)
    decodes = _decode_declared(sample, effective_charset_raw, truncated) is not None

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
        and not _encodings_compatible(declared_canonical, detected_canonical, sample, truncated)
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


def _encodings_compatible(declared: str, detected: str, sample: bytes, truncated: bool) -> bool:
    """
    Return True if decoding `sample` with `declared` and with `detected`
    yields the same text. This catches cases where chardet picks a
    different name (e.g. windows-1252 vs iso-8859-1) for content that is
    identical under both.

    If `sample` may be truncated, its tail is trimmed by a safety margin
    first: declared and detected encodings can have different maximum
    sequence lengths, so a split multi-byte character at the very end can
    make one decode "swallow" the incomplete tail while the other reads
    it as one or more extra characters -- a spurious divergence that has
    nothing to do with whether the encodings actually agree. If there
    isn't enough sample left to trim safely, the comparison is skipped
    (treated as compatible) rather than risking that false divergence.
    """
    if truncated:
        if len(sample) <= TRUNCATION_SAFETY_MARGIN:
            return True
        sample = sample[:-TRUNCATION_SAFETY_MARGIN]
    try:
        declared_text = sample.decode(declared, errors="strict")
        detected_text = sample.decode(detected, errors="strict")
    except (UnicodeDecodeError, LookupError):
        return False
    return declared_text == detected_text


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
