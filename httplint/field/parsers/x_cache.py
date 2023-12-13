from httplint.field import HttpField


class x_cache(HttpField):
    canonical_name = "X-Cache"
    description = """\
The `X-Cache` response header is used by some caches to indicate whether or not the response was
served from cache; if it contains `HIT`, it was."""
    reference = "https://lyte.id.au/2014/08/28/x-cache-and-x-cache-lookupheaders/"
    syntax = False
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
