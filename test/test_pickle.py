import pickle
from httplint.message import HttpRequestLinter, HttpResponseLinter

def test_pickle_request():
    linter = HttpRequestLinter()
    linter.process_request_topline(b"GET", b"/", b"HTTP/1.1")
    linter.process_headers([(b"content-type", b"text/plain")])
    linter.feed_content(b"foo")
    linter.finish_content(True)

    dumped = pickle.dumps(linter)
    loaded = pickle.loads(dumped)

    assert loaded.method == "GET"
    assert loaded.headers.parsed["content-type"] == ("text/plain", {})
    assert loaded.content_sample == b"foo"


def test_pickle_response():
    linter = HttpResponseLinter()
    linter.process_response_topline(b"HTTP/1.1", b"200", b"OK")
    linter.process_headers([(b"content-type", b"text/plain")])
    linter.feed_content(b"bar")
    linter.finish_content(True)

    dumped = pickle.dumps(linter)
    loaded = pickle.loads(dumped)

    assert loaded.status_code == 200
    assert loaded.headers.parsed["content-type"] == ("text/plain", {})
    assert loaded.content_sample == b"bar"
