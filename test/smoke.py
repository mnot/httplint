#!/usr/bin/env python3

from httplint.message import HttpResponseLinter

version = b"HTTP/1.1"
status_code = b"200"
status_phrase = b"OK"
raw_headers = [
    [b"Content-Type", b"text/html"],
    [b"Cache-Control", b"max-age=60"],
    [b"Content-Length", b"233"]
]
content_chunks = [
    b"this is a test",
    b"please ignore."
]

linter = HttpResponseLinter()
linter.process_response_topline(version, status_code, status_phrase)
linter.process_headers(raw_headers)
for chunk in content_chunks:
    linter.feed_content(chunk)
linter.finish_content(True)

for note in linter.notes.notes:
    print(note)
