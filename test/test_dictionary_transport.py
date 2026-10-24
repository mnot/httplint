import unittest
from httplint.message import HttpRequestLinter, HttpResponseLinter
from httplint.field.parsers.available_dictionary import AVAILABLE_DICTIONARY_MISSING_AE
from httplint.field.parsers.content_encoding import DICTIONARY_COMPRESSED_MISSING_VARY

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

    def test_request_missing_ae_text(self):
        for accept_encoding in (None, b"gzip", b"dcb;q=0", b"*, dcb;q=0, dcz;q=0"):
            with self.subTest(accept_encoding=accept_encoding):
                linter = HttpRequestLinter()
                linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
                headers = [
                    (b"Available-Dictionary", b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:")
                ]
                if accept_encoding is not None:
                    headers.append((b"Accept-Encoding", accept_encoding))
                linter.process_headers(headers)
                linter.finish_content(True)

                notes = [n for n in linter.notes if isinstance(n, AVAILABLE_DICTIONARY_MISSING_AE)]
                self.assertEqual(len(notes), 1)
                summary = notes[0].summary
                detail = " ".join(str(notes[0].detail).split())
                self.assertIn("can't be used", summary)
                self.assertIn("doesn't list dcb or dcz as acceptable", summary)
                self.assertNotIn("doesn't support", summary)
                self.assertIn(
                    "doesn't list <code>dcb</code> or <code>dcz</code> as acceptable", detail
                )
                self.assertIn("<code>q</code> value of 0", detail)
                self.assertIn("rfc9842.html#section-6.1", detail)
                self.assertNotIn("MUST", detail)
                self.assertNotIn("requires", detail)

    def test_request_q_zero_one_listed(self):
        linter = HttpRequestLinter()
        linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
        linter.process_headers([
            (b"Available-Dictionary", b":pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:"),
            (b"Accept-Encoding", b"dcb;q=0, dcz")
        ])
        linter.finish_content(True)

        self.assertFalse(any(isinstance(n, AVAILABLE_DICTIONARY_MISSING_AE) for n in linter.notes))

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
