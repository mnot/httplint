import unittest
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.field.notes import MISSING_USER_AGENT

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

if __name__ == "__main__":
    unittest.main()
