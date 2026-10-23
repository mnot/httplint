"""
Regex for RFC8288

These regex are directly derived from the collected ABNF in RFC8288.

    <https://www.rfc-editor.org/rfc/rfc8288#section-3>

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name


from .rfc3986 import URI_reference
from .rfc9110 import BWS, OWS, list_rule, quoted_string, token

SPEC_URL = "http://httpwg.org/specs/rfc8288"

#  link-param = token BWS [ "=" BWS ( token / quoted-string ) ]

#
# The first BWS is inside the optional group: outside it, "a ;a ;a" is ambiguous against the
# "OWS ;" in link-value, and backtracking is exponential on non-matching input. The accepted
# language is the same.

link_param = rf"(?: {token} (?: {BWS} = {BWS} (?: {token} | {quoted_string} ) )? )"

#  link-value = "<" URI-Reference ">" *( OWS ";" OWS link-param )

link_value = rf"(?: < {URI_reference} > (?: {OWS} ; {OWS} {link_param} )* )"

#  Link       = #link-value

Link = list_rule(link_value)
