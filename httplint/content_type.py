import sniffpy

from httplint.note import Note, categories, levels
from httplint.types import LinterProtocol


class CONTENT_TYPE_MISMATCH(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The content doesn't match the declared Content-Type."
    _text = """\
The `Content-Type` header declares the content as `%(declared_type)s`, but it looks like
`%(sniffed_type)s`."""


def verify_content_type(linter: LinterProtocol) -> None:
    """
    Verify that the content matches the declared Content-Type.
    """
    if not linter.content_hash:
        return

    # Don't verify content type for responses that don't carry a full representation
    status_code = getattr(linter, "status_code", None)
    if status_code in [204, 205, 304, 206] + list(range(100, 199)) or getattr(
        linter, "is_head_response", False
    ):
        return

    # Get the declared content type
    if "content-type" not in linter.headers.parsed:
        return
    declared_type = linter.headers.parsed["content-type"][0]
    if not declared_type:
        return

    try:
        sniffed_type = sniffpy.sniff(linter.content_sample, declared_type)
    except Exception:  # pylint: disable=broad-except
        # If sniffpy fails (e.g. invalid declared type), we can't verify.
        return

    if str(sniffed_type) != declared_type:
        # workaround for https://github.com/mnot/httplint/issues/112
        if declared_type == "text/html" and str(sniffed_type) in [
            "application/rss+xml",
            "application/atom+xml",
        ]:
            return
        linter.notes.add(
            "content-type",
            CONTENT_TYPE_MISMATCH,
            declared_type=declared_type,
            sniffed_type=str(sniffed_type),
        )
