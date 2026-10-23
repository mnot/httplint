import unittest

from httplint.field.utils import is_secure, resolve_url


class ResolveUrlTest(unittest.TestCase):
    def test_relative(self) -> None:
        resolved = resolve_url("../c", "https://example.com/a/b")
        assert resolved is not None
        self.assertEqual(resolved.geturl(), "https://example.com/c")

    def test_empty_base(self) -> None:
        resolved = resolve_url("http://example.com/x")
        assert resolved is not None
        self.assertEqual(resolved.netloc, "example.com")

    def test_malformed_ipv6(self) -> None:
        for url in ("http://[", "http://[::1", "http://[::1]x"):
            self.assertIsNone(resolve_url(url))
            self.assertIsNone(resolve_url(url, "https://example.com/"))

    def test_is_secure(self) -> None:
        for url, secure in [
            ("https://example.com/", True),
            ("WSS://example.com/", True),
            ("http://example.com/", False),
            ("ws://example.com/", False),
            ("/relative", False),
        ]:
            resolved = resolve_url(url)
            assert resolved is not None
            self.assertEqual(is_secure(resolved), secure, url)
