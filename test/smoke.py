#!/usr/bin/env python3

from httplint import HttpResponseLinter, Notes

notes = Notes()
linter = HttpResponseLinter(notes=notes)
linter.process_response_topline(b'HTTP/1.1', b'200', b'OK')
linter.process_headers([
  (b'Content-Type', b'text/plain'),
  (b'Content-Length', b'10'),
  (b'Cache-Control', b'max-age=60')
])
linter.feed_content(b'12345')
linter.feed_content(b'67890')
linter.finish_content(True)

for note in notes:
  print(note.summary)
