from typing import TYPE_CHECKING

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


if TYPE_CHECKING:
    from httplint.field.tests import FieldTest
else:
    try:
        from httplint.field.tests import FieldTest
    except ImportError:
        # satisfy discovery if not running as a test
        class FieldTest:  # type: ignore
            def setUp(self) -> None:
                pass


# pylint: disable=attribute-defined-outside-init
class TestVerifyContentType(FieldTest):
    def setUp(self) -> None:
        super().setUp()
        self.message.content_hash = b"hash"

    def check(
        self,
        content: bytes,
        declared_type: str | None,
        expected_notes: list[type[Note]] | None = None,
        status_code: int = 200,
        is_head_response: bool = False,
    ) -> None:
        self.message.content_sample = content
        if hasattr(self.message, "status_code"):
            setattr(self.message, "status_code", status_code)
        if hasattr(self.message, "is_head_response"):
            setattr(self.message, "is_head_response", is_head_response)
        if declared_type:
            self.inputs = [declared_type.encode("ascii")]
        else:
            self.inputs = []
        self.expected_notes = expected_notes or []
        self.test_header()

    def test_match(self) -> None:
        self.check(b"Hello world", "text/plain")

    def test_mismatch(self) -> None:
        self.check(b"Hello world", "image/png", [CONTENT_TYPE_MISMATCH])

    def test_missing_content_type(self) -> None:
        self.check(b"Hello world", None)

    def test_empty_content(self) -> None:
        self.check(b"", "text/plain")

    def test_long_content_match(self) -> None:
        self.check(b"a" * 2048, "text/plain")

    def test_long_content_mismatch(self) -> None:
        self.check(b"a" * 2048, "image/png", [CONTENT_TYPE_MISMATCH])

    def test_304_not_modified(self) -> None:
        self.check(b"", "image/png", status_code=304)

    def test_206_partial_content(self) -> None:
        self.check(b"some partial content", "image/png", status_code=206)

    def test_204_no_content(self) -> None:
        self.check(b"", "image/png", status_code=204)

    def test_head_request(self) -> None:
        self.check(b"", "image/png", is_head_response=True)

    def test_mimesniff_types(self) -> None:
        cases = [
            (b"<!DOCTYPE html>", "text/html"),
            (b"<html><head></head><body></body></html>", "text/html"),
            (b"\xef\xbb\xbf<!DOCTYPE html>", "text/html"),
            (b"<?xml version='1.0'?>", "text/xml"),
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"GIF87a", "image/gif"),
            (b"GIF89a", "image/gif"),
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"RIFF....WEBPVP8 ", "image/webp"),
            (b"%PDF-1.4", "application/pdf"),
            (b"%!PS-Adobe-", "application/postscript"),
            (b"Simple text", "text/plain"),
        ]

        for content, mime_type in cases:
            with self.subTest(mime_type=mime_type):
                self.setUp()
                self.check(content, mime_type)
