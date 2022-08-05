#!/usr/bin/env python3

from httplint.message import HttpResponse

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

m = HttpResponse()
m.process_top_line(version, status_code, status_phrase)
m.process_headers(raw_headers)
for chunk in content_chunks:
    m.feed_content(chunk)
m.finish_content(True)

for note in m.notes.notes:
    print(note)
