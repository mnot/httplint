import unittest
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.field.notes import (
    AVAILABLE_DICTIONARY_MISSING_AE,
    DICTIONARY_COMPRESSED_MISSING_VARY,
)

class TestDictionaryTransport(unittest.TestCase):
    def test_request_valid(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([
            (b"Available-Dictionary", b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"),
            (b"Accept-Encoding", b"dcb, gzip")
        ])
        linter.finish_content(True)
        
        self.assertFalse(any(n.category == AVAILABLE_DICTIONARY_MISSING_AE.category and 
                             n.level == AVAILABLE_DICTIONARY_MISSING_AE.level and 
                             n._summary == AVAILABLE_DICTIONARY_MISSING_AE._summary 
                             for n in linter.notes))

    def test_request_missing_ae(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([
            (b"Available-Dictionary", b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:")
        ])
        linter.finish_content(True)
        
        self.assertTrue(any(n.category == AVAILABLE_DICTIONARY_MISSING_AE.category and 
                            n.level == AVAILABLE_DICTIONARY_MISSING_AE.level and 
                            n._summary == AVAILABLE_DICTIONARY_MISSING_AE._summary 
                            for n in linter.notes))

    def test_request_wrong_ae(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([
            (b"Available-Dictionary", b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"),
            (b"Accept-Encoding", b"gzip, br")
        ])
        linter.finish_content(True)
        
        self.assertTrue(any(n.category == AVAILABLE_DICTIONARY_MISSING_AE.category and 
                            n.level == AVAILABLE_DICTIONARY_MISSING_AE.level and 
                            n._summary == AVAILABLE_DICTIONARY_MISSING_AE._summary 
                            for n in linter.notes))

    def test_response_valid(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([
            (b"Content-Encoding", b"dcb"),
            (b"Vary", b"Available-Dictionary"),
            (b"Cache-Control", b"max-age=60")
        ])
        linter.finish_content(True)
        
        self.assertFalse(any(n.category == DICTIONARY_COMPRESSED_MISSING_VARY.category and 
                             n.level == DICTIONARY_COMPRESSED_MISSING_VARY.level and 
                             n._summary == DICTIONARY_COMPRESSED_MISSING_VARY._summary 
                             for n in linter.notes))

    def test_response_missing_vary(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([
            (b"Content-Encoding", b"dcb"),
            (b"Cache-Control", b"max-age=60")
        ])
        linter.finish_content(True)
        
        self.assertTrue(any(n.category == DICTIONARY_COMPRESSED_MISSING_VARY.category and 
                            n.level == DICTIONARY_COMPRESSED_MISSING_VARY.level and 
                            n._summary == DICTIONARY_COMPRESSED_MISSING_VARY._summary 
                            for n in linter.notes))

    def test_response_uncacheable(self):
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        linter.process_headers([
            (b"Content-Encoding", b"dcb"),
            (b"Cache-Control", b"no-store")
        ])
        linter.finish_content(True)
        
        self.assertFalse(any(n.category == DICTIONARY_COMPRESSED_MISSING_VARY.category and 
                             n.level == DICTIONARY_COMPRESSED_MISSING_VARY.level and 
                             n._summary == DICTIONARY_COMPRESSED_MISSING_VARY._summary 
                             for n in linter.notes))

if __name__ == "__main__":
    unittest.main()
