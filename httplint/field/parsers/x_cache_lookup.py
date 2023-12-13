from httplint.field import HttpField


class x_cache_lookup(HttpField):
    canonical_name = "X-Cache-Lookup"
    description = """\
The `X-Cache-Lookup` response header is used by some caches to show whether there was a response in
cache for this URL; if it contains `HIT`, it was in cache (but not necessarily used)."""
    reference = "https://lyte.id.au/2014/08/28/x-cache-and-x-cache-lookupheaders/"
    syntax = False
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
