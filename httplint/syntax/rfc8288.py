"""
Regex for RFC8288

These regex are directly derived from the collected ABNF in RFC8288.

    <https://www.rfc-editor.org/rfc/rfc8288#section-3>

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name


from .rfc3986 import URI, URI_reference
from .rfc5234 import DIGIT, SP
from .rfc5646 import Language_Tag
from .rfc6838 import subtype_name, type_name
from .rfc9110 import BWS, OWS, list_rule, quoted_string, token

SPEC_URL = "http://httpwg.org/specs/rfc8288"

#  link-param = token BWS [ "=" BWS ( token / quoted-string ) ]

#
# The first BWS is inside the optional group: outside it, "a ;a ;a" is ambiguous against the
# "OWS ;" in link-value, and backtracking is exponential on non-matching input. link-value
# accepts the same language either way, because its "OWS ;" covers the trailing BWS; this
# rule on its own no longer matches a token followed by BWS ("a ").

link_param = rf"(?: {token} (?: {BWS} = {BWS} (?: {token} | {quoted_string} ) )? )"

#  link-value = "<" URI-Reference ">" *( OWS ";" OWS link-param )

link_value = rf"(?: < {URI_reference} > (?: {OWS} ; {OWS} {link_param} )* )"

#  Link       = #link-value

Link = list_rule(link_value)


# The rules below are in the prose of RFC 8288 Sections 3.2 to 3.4.1, not in the ABNF block of
# Section 3. None is used by a field parser yet.

#  LOALPHA is not defined in RFC 8288; it is RFC 2616's "any US-ASCII lower-case letter". Link
#  relation types are compared case-insensitively (Section 2.1.1), but reg-rel-type is written
#  with lower-case letters only, and is transcribed that way.

LOALPHA = r"(?-i:[a-z])"

#  reg-rel-type   = LOALPHA *( LOALPHA / DIGIT / "." / "-" )

reg_rel_type = rf"(?: {LOALPHA} (?: {LOALPHA} | {DIGIT} | \. | \- )* )"

#  ext-rel-type   = URI ; Section 3 of [RFC3986]

ext_rel_type = URI

#  relation-type  = reg-rel-type / ext-rel-type

relation_type = rf"(?: {reg_rel_type} | {ext_rel_type} )"

#  The value of the "rel" and "rev" parameters (Section 3.3; the RFC gives it no name):
#
#  relation-type *( 1*SP relation-type )

rel_param_value = rf"(?: {relation_type} (?: {SP}+ {relation_type} )* )"

#  The value of the "anchor" parameter (Section 3.2):
#
#  URI-Reference ; Section 4.1 of [RFC3986]

anchor_param_value = URI_reference

#  The value of the "hreflang" parameter (Section 3.4.1):
#
#  Language-Tag

hreflang_param_value = Language_Tag

#  The value of the "type" parameter (Section 3.4.1):
#
#  type-name "/" subtype-name ; see Section 4.2 of [RFC6838]

type_param_value = rf"(?: {type_name} / {subtype_name} )"

#  The value of the "media" parameter is a media-query-list, which RFC 8288 does not define (it
#  refers to HTML), so there is no rule for it. "title*" takes an ext-value (RFC 8187); see rfc5987.
