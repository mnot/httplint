import gzip
import hashlib
from typing import Any

import pytest

from httplint.message import HttpResponseLinter


@pytest.fixture
def fips_hashlib(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make hashlib.new("md5") fail as it does on FIPS-enabled OpenSSL builds."""
    real_new = hashlib.new

    def fips_new(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "md5" and kwargs.get("usedforsecurity", True):
            raise ValueError("[digital envelope routines] unsupported")
        return real_new(name, *args, **kwargs)

    monkeypatch.setattr(hashlib, "new", fips_new)


def test_construct_under_fips(fips_hashlib: None) -> None:
    HttpResponseLinter()


def test_digests_unchanged_under_fips(fips_hashlib: None) -> None:
    data = b"Hello, Gzip!"
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(b"Content-Encoding", b"gzip")])
    linter.feed_content(gzip.compress(data))
    linter.finish_content(True)

    expected = hashlib.md5(data).digest()  # nosec: fingerprint only
    assert linter.decoded.hash == expected
    assert linter.content_hash == hashlib.md5(gzip.compress(data)).digest()
