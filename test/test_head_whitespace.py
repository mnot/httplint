"""
OWS before the ";" that starts a field's parameters isn't part of the value before it (#330).

End to end: the false notes the issue reports, which came from the coding or disposition type
parsing with a trailing space.
"""

import unittest
from typing import Iterable, List

from httplint.field.parsers.content_disposition import DISPOSITION_UNKNOWN
from httplint.field.parsers.content_encoding import ENCODING_UNWANTED
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.note import Note


def all_notes(linter: HttpResponseLinter) -> List[Note]:
    found: List[Note] = []

    def collect(notes: Iterable[Note]) -> None:
        for note in notes:
            found.append(note)
            collect(note.subnotes)

    collect(linter.notes)
    return found


def response_to(accept_encoding: bytes, content_encoding: bytes) -> HttpResponseLinter:
    request = HttpRequestLinter()
    request.process_request_topline(b"GET", b"http://example.com/", b"HTTP/1.1")
    request.process_headers([(b"Accept-Encoding", accept_encoding)])
    response = HttpResponseLinter()
    response.request = request
    response.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    response.process_headers([(b"Content-Encoding", content_encoding)])
    return response


class AcceptEncodingWeightTest(unittest.TestCase):
    def unwanted(self, accept_encoding: bytes, content_encoding: bytes = b"gzip") -> int:
        response = response_to(accept_encoding, content_encoding)
        return sum(isinstance(note, ENCODING_UNWANTED) for note in all_notes(response))

    def test_space_before_semicolon(self) -> None:
        self.assertEqual(self.unwanted(b"gzip ; q=0.5"), 0)

    def test_tab_before_semicolon(self) -> None:
        self.assertEqual(self.unwanted(b"gzip\t;\tq=0.5"), 0)

    def test_no_whitespace_before_semicolon(self) -> None:
        "Guard: passes on main."
        self.assertEqual(self.unwanted(b"gzip;q=0.5"), 0)

    def test_q_zero_still_unwanted(self) -> None:
        "Guard: the coding is still matched, so a refusal after OWS is still reported."
        self.assertEqual(self.unwanted(b"gzip ; q=0"), 1)
        self.assertEqual(self.unwanted(b"gzip\t;q=0"), 1)

    def test_other_coding_still_unwanted(self) -> None:
        "Guard: passes on main."
        self.assertEqual(self.unwanted(b"br ; q=0.5"), 1)


class ContentDispositionTypeTest(unittest.TestCase):
    def notes(self, value: bytes) -> List[Note]:
        response = HttpResponseLinter()
        response.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        response.process_headers([(b"Content-Disposition", value)])
        return all_notes(response)

    def unknown(self, value: bytes) -> int:
        return sum(isinstance(note, DISPOSITION_UNKNOWN) for note in self.notes(value))

    def test_space_before_semicolon(self) -> None:
        self.assertEqual(self.unknown(b"attachment ; filename=x"), 0)

    def test_tab_before_semicolon(self) -> None:
        self.assertEqual(self.unknown(b"attachment\t;\tfilename=x"), 0)

    def test_no_whitespace_before_semicolon(self) -> None:
        "Guard: passes on main."
        self.assertEqual(self.unknown(b"attachment;filename=x"), 0)

    def test_unknown_type_still_reported(self) -> None:
        "Guard: passes on main."
        self.assertEqual(self.unknown(b"form-data ; filename=x"), 1)


if __name__ == "__main__":
    unittest.main()
