import unittest
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.field.notes import MISSING_USER_AGENT
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

if __name__ == "__main__":
    unittest.main()
