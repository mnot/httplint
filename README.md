
# httplint

This Python library _lints_ HTTP messages; it checks them for correctness and reports any issues it finds.

It has been extracted from [REDbot](https://redbot.org/), which will eventually depend upon it. Unlike REDbot, it does not perform any 'active' checks by making requests to the network, and it does not have a Web user interface.


## Using httplint as a Library

httplint exposes two classes for linting: `HttpRequestLinter` and `HttpResponseLinter`. They expose the following methods for telling the linter about the HTTP message:

* As appropriate:
  * `process_request_topline`, which takes three `bytes` arguments: `method`, `uri`, and `version`
  * `process_response_topline`, which takes three `bytes` arguments: `version`, `status_code`, and `status_phrase`
* `process_headers` for the headers, taking a list of (`name`, `value`) tuples (both `bytes`)
* `feed_content` for the body (which can be called zero to many times), taking an `inbytes` argument
* `finish_content` when done, which has two arguments; a `bool` indicating whether the response was complete, and an optional list of tuples for the trailers, in the same format that `process_headers` takes.

For example:

~~~ python
from httplint import HttpResponseLinter

linter = HttpResponseLinter()
linter.process_response_topline(b'HTTP/1.1', b'200', b'OK')
linter.process_headers([
  (b'Content-Type', b'text/plain'),
  (b'Content-Length', b'10'),
  (b'Cache-Control', b'max-age=60')
])
linter.feed_content(b'12345')
linter.feed_content(b'67890')
linter.finish_content(True)
~~~

## Using httplint from the Command Line

httplint can also be used from the command line. For example:

~~~
> curl -s -i --raw https://www.mnot.net/ | httplint -n
* The Content-Length header is correct.
* The resource last changed 8 days 6 hr ago.
* This response allows all caches to store it.
* The server's clock is correct.
* This response is fresh until 3 hr from now.
* This response may still be served by a cache once it becomes stale.
~~~


### Interpreting Notes

Once a message has been linted, the results will appear on the `notes` property. This is a list of `Note` objects, each having the following attributes:

* `category` - the Note's category; see `note.categories`
* `level` - see `note.levels`
* `summary` - a brief, one-line description of the note
* `detail` - a longer explanation

Note that `summary` is textual, and needs to be escaped in a markup environment; `detail`, however, is already escaped HTML.

Continuing our example:

~~~ python
for note in linter.notes:
  print(note.summary)
~~~

and the output should be:

~~~
The Content-Length header is correct.
This response allows all caches to store it.
This response doesn't have a Date header.
This response is fresh until 1 min from now.
This response may still be served by a cache once it becomes stale.
~~~

### Field Descriptions

The description of any field can be found by calling `get_field_description`. For example:

~~~ python
>>> from httplint import get_field_description
>>> get_field_description("Allow")
'The `Allow` response header advertises the set of methods that are supported by the resource.'
~~~

If a description cannot be found it will return `None`.
