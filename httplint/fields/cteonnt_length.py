from httplint.fields import HttpField


class cteonnt_length(HttpField):
    description = """\
The `%(field_name)s` field usually means that a HTTP load balancer, proxy or
other intermediary in front of the server has rewritten the `Content-Length`
header, to allow it to insert its own.

Usually, this is done because an intermediary has dynamically compressed the
response.

It takes this form because the most efficient way of assuring that clients
don't see the header is to rearrange or change individual characters in its
name. """
