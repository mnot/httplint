import sys
import types
import unittest
import unittest.mock
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.message import MISSING_USER_AGENT
from httplint.field.finder import HttpFieldFinder
from httplint.field.parsers.referer import (
    REFERER_SECURE_TO_INSECURE,
    REFERER_SECURE_TO_DIFFERENT_ORIGIN,
)

class TestMessageLinter(unittest.TestCase):
    def test_request_missing_user_agent(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([])
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertTrue(any(n.category == MISSING_USER_AGENT.category and 
                            n.level == MISSING_USER_AGENT.level and 
                            n._summary == MISSING_USER_AGENT._summary 
                            for n in notes), "MISSING_USER_AGENT note not found")

    def test_request_present_user_agent(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([(b"User-Agent", b"TestAgent/1.0")])
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertFalse(any(n.category == MISSING_USER_AGENT.category and 
                             n.level == MISSING_USER_AGENT.level and 
                             n._summary == MISSING_USER_AGENT._summary 
                             for n in notes), "MISSING_USER_AGENT note found when header is present")

    def test_response_missing_user_agent(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([])
        linter.finish_content(True)

        notes = linter.notes
        self.assertFalse(any(n.category == MISSING_USER_AGENT.category and 
                             n.level == MISSING_USER_AGENT.level and 
                             n._summary == MISSING_USER_AGENT._summary 
                             for n in notes), "MISSING_USER_AGENT note found in response")

    def test_secure_to_insecure(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"http://example.com/", b"HTTP/1.1")
        linter.process_headers([(b"Referer", b"https://secure.example.com/")])
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertTrue(any(n.category == REFERER_SECURE_TO_INSECURE.category and 
                            n.level == REFERER_SECURE_TO_INSECURE.level and 
                            n._summary == REFERER_SECURE_TO_INSECURE._summary 
                            for n in notes), "REFERER_SECURE_TO_INSECURE note not found")

    def test_secure_to_secure_same_origin(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"https://example.com/foo", b"HTTP/1.1")
        linter.process_headers([(b"Referer", b"https://example.com/bar")])
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertFalse(any(n.category == REFERER_SECURE_TO_INSECURE.category for n in notes))
        self.assertFalse(any(n.category == REFERER_SECURE_TO_DIFFERENT_ORIGIN.category for n in notes))

    def test_secure_to_secure_diff_origin(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"https://other.example.com/", b"HTTP/1.1")
        linter.process_headers([(b"Referer", b"https://secure.example.com/")])
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertTrue(any(n.category == REFERER_SECURE_TO_DIFFERENT_ORIGIN.category and 
                            n.level == REFERER_SECURE_TO_DIFFERENT_ORIGIN.level and 
                            n._summary == REFERER_SECURE_TO_DIFFERENT_ORIGIN._summary 
                            for n in notes), "REFERER_SECURE_TO_DIFFERENT_ORIGIN note not found")

    def test_insecure_to_insecure(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"http://example.com/", b"HTTP/1.1")
        linter.process_headers([(b"Referer", b"http://other.example.com/")])
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertFalse(any(n.category == REFERER_SECURE_TO_INSECURE.category for n in notes))
        self.assertFalse(any(n.category == REFERER_SECURE_TO_DIFFERENT_ORIGIN.category for n in notes))

    def test_insecure_to_secure(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"https://example.com/", b"HTTP/1.1")
        linter.process_headers([(b"Referer", b"http://insecure.example.com/")])
        linter.finish_content(True)
        
        notes = linter.notes
        self.assertFalse(any(n.category == REFERER_SECURE_TO_INSECURE.category for n in notes))
        self.assertFalse(any(n.category == REFERER_SECURE_TO_DIFFERENT_ORIGIN.category for n in notes))


class TestFieldSection(unittest.TestCase):
    @staticmethod
    def _subjects(linter):
        return [(n.subject, type(n).__name__) for n in linter.notes]

    def test_offset_after_rejected_field(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"1.1")
        linter.process_headers([(b"Age", b"abc"), (b"Accept", b"text/html;;q=x")])
        subjects = self._subjects(linter)
        self.assertIn(("offset-0", "RESPONSE_HDR_IN_REQUEST"), subjects)
        self.assertIn(("offset-1", "BAD_Q_VALUE"), subjects)
        self.assertNotIn(("offset-0", "BAD_Q_VALUE"), subjects)

    def test_field_too_large_on_rejected_field(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"1.1")
        linter.process_headers([(b"Age", b"1" * 9000)])
        self.assertIn(("offset-0", "FIELD_TOO_LARGE"), self._subjects(linter))

    def test_field_name_whitespace(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b" Date ", b"Mon, 01 Jan 2024 00:00:00 GMT")])
        subjects = self._subjects(linter)
        self.assertIn(("offset-0", "FIELD_NAME_WHITESPACE"), subjects)
        self.assertNotIn(("offset-0", "FIELD_NAME_BAD_SYNTAX"), subjects)
        self.assertEqual(linter.headers.text[0][0], "Date")
        self.assertIn("date", linter.headers.handlers)
        self.assertNotIn(" date ", linter.headers.handlers)
        self.assertIn("date", linter.headers.parsed)
        self.assertNotIn("DATE_CLOCKLESS", [name for _, name in subjects])

    def test_raw_fields_name_recoverable_and_aligned(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers(
            [(b"Server", b"x"), (b" Date ", b"Mon, 01 Jan 2024 00:00:00 GMT"), (b"Age", b"1")]
        )
        headers = linter.headers
        self.assertEqual(headers.raw_fields[1][0], b" Date ")
        self.assertEqual(headers.text[1][0], "Date")
        self.assertEqual(len(headers.raw_fields), len(headers.text))
        note = [n for n in linter.notes if type(n).__name__ == "FIELD_NAME_WHITESPACE"][0]
        self.assertEqual(note.subject, "offset-1")
        self.assertEqual(note.vars["field_name"], "Date")
        self.assertEqual(note.vars["sent_name"], " Date ")

    def test_raw_fields_value_recoverable(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Server", b"caf\xe9")])
        headers = linter.headers
        self.assertEqual(headers.text[0], ("Server", "caf\xe9"))
        self.assertEqual(headers.raw_fields[0], (b"Server", b"caf\xe9"))

    def test_raw_fields_aligned_after_rejected_field(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"1.1")
        raw = [(b"Age", b"abc"), (b" Accept ", b"text/html;;q=x"), (b"Bad Name", b"v")]
        linter.process_headers(raw)
        headers = linter.headers
        self.assertEqual(headers.raw_fields, raw)
        self.assertEqual([n for n, _ in headers.text], ["Age", "Accept", "Bad Name"])
        subjects = self._subjects(linter)
        self.assertIn(("offset-1", "BAD_Q_VALUE"), subjects)
        self.assertIn(("offset-2", "FIELD_NAME_BAD_SYNTAX"), subjects)

    def test_whitespace_only_field_name(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b" ", b"foo")])
        names = [name for _, name in self._subjects(linter)]
        self.assertNotIn("FIELD_NAME_WHITESPACE", names)
        self.assertIn("FIELD_NAME_BAD_SYNTAX", names)

    def test_field_name_without_whitespace_has_no_note(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([(b"Date", b"Mon, 01 Jan 2024 00:00:00 GMT")])
        self.assertNotIn("FIELD_NAME_WHITESPACE", [name for _, name in self._subjects(linter)])


class TestFieldFinder(unittest.TestCase):
    def test_non_field_attribute_ignored(self):
        module = types.ModuleType("httplint.field.parsers.fake_helper")
        module.fake_helper = lambda: None
        with unittest.mock.patch.dict(sys.modules, {module.__name__: module}):
            self.assertIsNone(HttpFieldFinder.find_handler_class("Fake-Helper"))

    def test_non_subclass_class_ignored(self):
        module = types.ModuleType("httplint.field.parsers.fake_class")
        module.fake_class = type("fake_class", (), {})
        with unittest.mock.patch.dict(sys.modules, {module.__name__: module}):
            self.assertIsNone(HttpFieldFinder.find_handler_class("Fake-Class"))

    def test_real_field_class_found(self):
        self.assertIsNotNone(HttpFieldFinder.find_handler_class("Content-Type"))


if __name__ == "__main__":
    unittest.main()
