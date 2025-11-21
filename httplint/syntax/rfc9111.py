"""
Regex for RFC9111
"""

# pylint: disable=invalid-name

from .rfc5234 import DIGIT, DQUOTE, SP
from .rfc9110 import (
    list_rule,
    pseudonym,
    quoted_string,
    token,
    HTTP_date,
    uri_host,
    port,
)

SPEC_URL = "http://httpwg.org/specs/rfc9111"


#   delta-seconds = 1*DIGIT

delta_seconds = rf"{DIGIT}+"

#   Age = delta-seconds

Age = delta_seconds

#   cache-directive = token [ "=" ( token / quoted-string ) ]

cache_directive = rf"(?: {token} (?: = (?: {token} | {quoted_string} ) )? )"

#   Cache-Control = [ cache-directive *( OWS "," OWS cache-directive ) ]

Cache_Control = list_rule(cache_directive)

#   Expires = HTTP-date

Expires = HTTP_date

#   extension-pragma = token [ "=" ( token / quoted-string ) ]

extension_pragma = rf"(?: {token} (?: = (?: {token} | {quoted_string} ) )? )"

#   pragma-directive = "no-cache" / extension-pragma

pragma_directive = rf"(?: no-cache | {extension_pragma} )"

#   Pragma = 1#pragma-directive
# Note: RFC 9111 defines Pragma as 1#pragma-directive, but doesn't show the ABNF
# for Pragma itself in the collected ABNF.
# We use the list_rule with minimum 1 as per RFC 9111.

Pragma = list_rule(pragma_directive, 1)

#   warn-code = 3DIGIT

warn_code = rf"{DIGIT}{{3}}"

#   warn-agent = ( uri-host [ ":" port ] ) / pseudonym

warn_agent = rf"(?: (?: {uri_host} (?: : {port} )? ) | {pseudonym} )"

#   warn-text = quoted-string

warn_text = quoted_string

#   warn-date = DQUOTE HTTP-date DQUOTE

warn_date = rf"(?: {DQUOTE} {HTTP_date} {DQUOTE} )"

#   warning-value = warn-code SP warn-agent SP warn-text [ SP warn-date ]

warning_value = (
    rf"(?: {warn_code} {SP} {warn_agent} {SP} {warn_text} (?: {SP} {warn_date} )? )"
)

#   Warning = 1#warning-value
# Note: RFC 9111 defines Warning as 1#warning-value, but doesn't show the ABNF
# for Warning itself in the collected ABNF.
# We use the list_rule with minimum 1 as per RFC 9111.

Warning_ = list_rule(warning_value, 1)
