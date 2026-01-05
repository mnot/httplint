from httplint.field.singleton_field import SingletonField
from httplint.syntax import rfc9110


class retry_after(SingletonField):
    canonical_name = "Retry-After"
    description = """\
The `Retry-After` response header can be used with a `503` (Service Unavailable) response to
indicate how long the service is expected to be unavailable to the requesting client.

The value of this field can be either a date or an integer number of seconds."""
    reference = f"{rfc9110.SPEC_URL}#field.retry-after"
    syntax = rfc9110.Retry_After
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
