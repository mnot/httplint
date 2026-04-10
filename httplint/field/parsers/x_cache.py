from httplint.field.list_field import HttpListField
from httplint.note import categories
from httplint.types import ResponseLinterProtocol


class x_cache(HttpListField[ResponseLinterProtocol]):
    canonical_name = "X-Cache"
    description = """\
The `X-Cache` response header is used by some caches to indicate whether or not the response was
served from cache; if it contains `HIT`, it was."""
    reference = "https://lyte.id.au/2014/08/28/x-cache-and-x-cache-lookupheaders/"
    syntax = False
    category = categories.CACHING
    deprecated = False
    no_coverage = True
    valid_in_requests = False
    valid_in_responses = True
