"""
Render tests for note text: broken links, typos, and Markdown that rendered wrongly.
"""

import re
import unittest
from typing import List, Tuple, Type

from httplint import HttpResponseLinter
from httplint.field.parsers.cache_status import CACHE_STATUS
from httplint.field.parsers.content_security_policy import CONTENT_SECURITY_POLICY
from httplint.field.parsers.cross_origin_embedder_policy import COEP_REQUIRE_CORP
from httplint.field.parsers.cross_origin_opener_policy import COOP_SAME_ORIGIN
from httplint.field.parsers.cross_origin_resource_policy import CORP_SAME_ORIGIN
from httplint.field.parsers.date import DATE_INCORRECT
from httplint.field.parsers.nel import NEL_BAD_VALUE
from httplint.field.parsers.proxy_status import PROXY_STATUS
from httplint.note import Note, Notes

Header = Tuple[bytes, bytes]


def _notes(headers: List[Header]) -> List[Note]:
    "All notes from linting a response with these headers, sub-notes flattened in."
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers(headers)
    linter.finish_content(True)
    out: List[Note] = []
    pending = list(linter.notes)
    while pending:
        note = pending.pop(0)
        out.append(note)
        pending.extend(note.subnotes)
    return out


def _one(headers: List[Header], note_class: Type[Note]) -> Note:
    found = [n for n in _notes(headers) if isinstance(n, note_class)]
    assert len(found) == 1, found
    return found[0]


class DateIncorrectLinkTest(unittest.TestCase):
    def test_ntp_link_has_a_clean_href_and_a_title(self) -> None:
        note = Notes({"field_name": "Date"}).add(
            "field-date", DATE_INCORRECT, clock_skew_string="a"
        )
        detail = str(note.detail)
        self.assertIn('href="http://en.wikipedia.org/wiki/Network_Time_Protocol"', detail)
        self.assertIn('title="Network Time Protocol"', detail)
        self.assertNotIn("Network_Time_Protocol Network", detail)


class NelBadValueTextTest(unittest.TestCase):
    def test_fraction_out_of_range(self) -> None:
        note = _one(
            [(b"NEL", b'{"report_to": "a", "max_age": 1, "success_fraction": 2.0}')],
            NEL_BAD_VALUE,
        )
        detail = str(note.detail)
        self.assertIn("it must be between 0.0 and 1.0", detail)
        self.assertNotIn("itmust", detail)
        self.assertEqual(detail.count("between 0.0 and 1.0"), 1)
        self.assertNotIn("Details:", detail)

    def test_negative_max_age_is_stated_once(self) -> None:
        note = _one([(b"NEL", b'{"report_to": "a", "max_age": -1}')], NEL_BAD_VALUE)
        detail = str(note.detail)
        self.assertEqual(detail.count("must not be negative"), 1)
        self.assertEqual(
            detail,
            "<p>The <code>max_age</code> key has an invalid value; it must not be negative.</p>",
        )


class StatusListRenderTest(unittest.TestCase):
    def _check_list(self, detail: str) -> None:
        self.assertIn("<ul>", detail)
        self.assertNotRegex(detail, r"(?m)^\* ")

    def test_cache_status_bullets_are_a_list(self) -> None:
        note = _one([(b"Cache-Status", b"Foo; hit; ttl=3, Bar; fwd=miss")], CACHE_STATUS)
        detail = str(note.detail)
        self._check_list(detail)
        self.assertEqual(detail.count("<ul>"), 2)
        self.assertIn("<p><strong><code>Foo</code></strong>:</p>\n<ul>", detail)
        self.assertIn("<li>The response was served from the cache.</li>", detail)

    def test_proxy_status_bullets_are_a_list(self) -> None:
        note = _one(
            [(b"Proxy-Status", b"Foo; error=dns_error, Bar; next-hop=x")],
            PROXY_STATUS,
        )
        detail = str(note.detail)
        self._check_list(detail)
        self.assertEqual(detail.count("<ul>"), 2)
        self.assertIn("<li>The proxy encountered a DNS error.</li>", detail)
        self.assertIn("<li>The next hop was <code>x</code>.</li>", detail)

    def test_proxy_status_inner_list_target_is_not_a_python_repr(self) -> None:
        note = _one([(b"Proxy-Status", b"(a b); next-hop=x")], PROXY_STATUS)
        detail = str(note.detail)
        self.assertIn("<strong><code>(a b)</code></strong>", detail)
        self.assertNotIn("Token(", detail)
        self.assertNotIn("{}", detail)

    def test_proxy_status_unknown_error_value_is_shown(self) -> None:
        "An error value with no description is listed as is."
        note = _one([(b"Proxy-Status", b"Foo; error=not_a_real_error")], PROXY_STATUS)
        self.assertIn(
            "<li><code>error</code>: <code>not_a_real_error</code></li>", str(note.detail)
        )


class ReportOnlyParagraphTest(unittest.TestCase):
    REPORT_ONLY = "Browsers will only report violations of this policy, not enforce it."

    def _check(self, headers: List[Header], note_class: Type[Note]) -> None:
        note = _one(headers, note_class)
        detail = str(note.detail)
        paragraphs = re.findall(r"<p>(.*?)</p>", detail, re.S)
        self.assertEqual(len(paragraphs), 2, detail)
        self.assertEqual(paragraphs[1], self.REPORT_ONLY)
        self.assertNotIn("Browsers", paragraphs[0])
        self.assertNotIn("\n\n", detail)

    def test_csp_report_only(self) -> None:
        self._check(
            [(b"Content-Security-Policy-Report-Only", b"default-src 'self'")],
            CONTENT_SECURITY_POLICY,
        )

    def test_coep_report_only(self) -> None:
        self._check(
            [(b"Cross-Origin-Embedder-Policy-Report-Only", b"require-corp")],
            COEP_REQUIRE_CORP,
        )

    def test_coop_report_only(self) -> None:
        self._check(
            [(b"Cross-Origin-Opener-Policy-Report-Only", b"same-origin")],
            COOP_SAME_ORIGIN,
        )

    def test_enforcing_headers_have_no_report_only_text(self) -> None:
        "Guard: the enforcing variants do not mention reporting."
        for headers, note_class in [
            ([(b"Content-Security-Policy", b"default-src 'self'")], CONTENT_SECURITY_POLICY),
            ([(b"Cross-Origin-Embedder-Policy", b"require-corp")], COEP_REQUIRE_CORP),
            ([(b"Cross-Origin-Opener-Policy", b"same-origin")], COOP_SAME_ORIGIN),
        ]:
            self.assertNotIn("Browsers will only report", str(_one(headers, note_class).detail))

    def test_corp_has_no_report_only_text(self) -> None:
        "Guard: also passes on main; covers removing the unused report_only_text variable."
        note = _one([(b"Cross-Origin-Resource-Policy", b"same-origin")], CORP_SAME_ORIGIN)
        detail = str(note.detail)
        self.assertNotIn("report", detail.lower())
        self.assertTrue(detail.rstrip().endswith("in supporting browsers.</p>"), detail)


if __name__ == "__main__":
    unittest.main()
