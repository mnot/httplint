from httplint.field.singleton_field import SingletonField


class p3p(SingletonField):
    canonical_name = "P3P"
    description = """\
The `P3P` response header allows a server to describe its privacy policy in a
machine-readable way. It has been deprecated, because client support was poor.
"""
    reference = "http://www.w3.org/TR/P3P/#syntax_ext"
    syntax = False
    deprecated = True
    valid_in_requests = False
    valid_in_responses = True
    no_coverage = True
