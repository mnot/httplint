import unittest
from httplint.message import HttpResponseLinter
from httplint.field.unnecessary import UNNECESSARY_HEADER

class TestUnnecessaryHeaders(unittest.TestCase):
    def test_unnecessary_headers(self) -> None:
        linter = HttpResponseLinter()
        linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
        headers = [
            (b"X-AspNet-Version", b"4.0.30319"),
            (b"X-Powered-By", b"ASP.NET"),
            (b"TCN", b"list"),
            (b"X-AspNetMvc-Version", b"5.2"),
            (b"X-Generator", b"Drupal 7"),
            (b"X-Drupal-Cache", b"HIT"),
            (b"X-Varnish", b"123456789"),
            (b"X-Mod-Pagespeed", b"1.13.35.2-0"),
            (b"X-Pingback", b"http://example.com/xmlrpc.php"),
            (b"X-Runtime", b"0.01234"),
            (b"X-Rack-Cache", b"miss"),
            (b"X-Content-Encoded-By", b"Joomla! 2.5"),
            (b"X-Backend-Server", b"server1"),
        ]
        linter.process_headers(headers)
        linter.finish_content(True)

        notes = [n.__class__ for n in linter.notes]
        self.assertIn(UNNECESSARY_HEADER, notes)
        # Check count of unnecessary headers
        unnecessary_notes = [
            n for n in linter.notes if isinstance(n, UNNECESSARY_HEADER)
        ]
        self.assertEqual(len(unnecessary_notes), len(headers))


if __name__ == "__main__":
    unittest.main()
