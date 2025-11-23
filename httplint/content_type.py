import unittest
from typing import TYPE_CHECKING, Any

import sniffpy  # type: ignore[import-untyped]

from httplint.note import Note, categories, levels

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class CONTENT_TYPE_MISMATCH(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The content doesn't match the declared Content-Type."
    _text = """\
The `Content-Type` header declares the content as `%(declared_type)s`, but it looks like
`%(sniffed_type)s`."""


def verify_content_type(linter: "HttpMessageLinter") -> None:
    """
    Verify that the content matches the declared Content-Type.
    """
    if not linter.content_hash:
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
        linter.notes.add(
            "content-type",
            CONTENT_TYPE_MISMATCH,
            declared_type=declared_type,
            sniffed_type=str(sniffed_type),
        )


class MockLinter:
    def __init__(self) -> None:
        self.content_hash: bytes = b"hash"
        self.headers = MockHeaders()
        self.content_sample: bytes = b""
        self.notes = MockNotes()


class MockHeaders:
    def __init__(self) -> None:
        self.parsed: dict = {}


class MockNotes:
    def __init__(self) -> None:
        self._notes: list = []

    def add(self, subject: str, note: type[Note], **kw: Any) -> None:
        self._notes.append(note)

    def __iter__(self) -> Any:
        return iter(self._notes)


class TestVerifyContentType(unittest.TestCase):
    def test_match(self) -> None:
        linter = MockLinter()
        linter.headers.parsed["content-type"] = ("text/plain", {})
        linter.content_sample = b"Hello world"
        verify_content_type(linter)  # type: ignore[arg-type]
        self.assertNotIn(CONTENT_TYPE_MISMATCH, linter.notes)

    def test_mismatch(self) -> None:
        linter = MockLinter()
        linter.headers.parsed["content-type"] = ("image/png", {})
        linter.content_sample = b"Hello world"
        verify_content_type(linter)  # type: ignore[arg-type]
        self.assertIn(CONTENT_TYPE_MISMATCH, linter.notes)

    def test_missing_content_type(self) -> None:
        linter = MockLinter()
        linter.content_sample = b"Hello world"
        verify_content_type(linter)  # type: ignore[arg-type]
        self.assertNotIn(CONTENT_TYPE_MISMATCH, linter.notes)

    def test_empty_content(self) -> None:
        linter = MockLinter()
        linter.headers.parsed["content-type"] = ("text/plain", {})
        linter.content_sample = b""
        verify_content_type(linter)  # type: ignore[arg-type]
        self.assertNotIn(CONTENT_TYPE_MISMATCH, linter.notes)

    def test_long_content_match(self) -> None:
        linter = MockLinter()
        linter.headers.parsed["content-type"] = ("text/plain", {})
        linter.content_sample = b"a" * 2048
        verify_content_type(linter)  # type: ignore[arg-type]
        self.assertNotIn(CONTENT_TYPE_MISMATCH, linter.notes)

    def test_long_content_mismatch(self) -> None:
        linter = MockLinter()
        linter.headers.parsed["content-type"] = ("image/png", {})
        linter.content_sample = b"a" * 2048
        verify_content_type(linter)  # type: ignore[arg-type]
        self.assertIn(CONTENT_TYPE_MISMATCH, linter.notes)

    def test_mimesniff_types(self) -> None:
        """
        Test various content types that should be correctly identified by WHATWG mimesniff.
        """
        cases = [
            (b"<!DOCTYPE html>", b"text/html"),
            (b"<html><head></head><body></body></html>", b"text/html"),
            (b"\xef\xbb\xbf<!DOCTYPE html>", b"text/html"),  # UTF-8 BOM
            (b"<?xml version='1.0'?>", b"text/xml"),
            (b"\x89PNG\r\n\x1a\n", b"image/png"),
            (b"GIF87a", b"image/gif"),
            (b"GIF89a", b"image/gif"),
            (b"\xff\xd8\xff", b"image/jpeg"),
            (b"RIFF....WEBPVP8 ", b"image/webp"),
            # (b"\x1a\x45\xdf\xa3", b"video/webm"),
            # EBML ID for WebM/Matroska (simplified) - sniffpy doesn't support this yet
            (b"%PDF-1.4", b"application/pdf"),
            (b"%!PS-Adobe-", b"application/postscript"),
            (b"Simple text", b"text/plain"),
        ]

        for content, mime_type in cases:
            with self.subTest(mime_type=mime_type):
                linter = MockLinter()
                linter.headers.parsed["content-type"] = (mime_type.decode("ascii"), {})
                linter.content_sample = content
                verify_content_type(linter)  # type: ignore[arg-type]
                self.assertNotIn(
                    CONTENT_TYPE_MISMATCH,
                    linter.notes,
                    f"Failed to match {mime_type!r} for content starting with {content[:10]!r}",
                )
