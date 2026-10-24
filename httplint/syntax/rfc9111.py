"""
Regex for RFC9111

These regex are directly derived from the collected ABNF in RFC9111 (Appendix A), with the
exception of Pragma and Warning: RFC 9111 has no ABNF for them (it deprecates Pragma, Section 5.4,
and obsoletes Warning, Section 5.5), so those rules are RFC 7234's (Section 5.4, Section 5.5 and
Appendix C).

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name

from .rfc3986 import host as uri_host
from .rfc3986 import port
from .rfc5234 import DIGIT, DQUOTE, SP
from .rfc9110 import (
    HTTP_date,
    list_rule,
    pseudonym,
    quoted_string,
    token,
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
#   (RFC 7234, Section 5.4)

extension_pragma = rf"(?: {token} (?: = (?: {token} | {quoted_string} ) )? )"

#   pragma-directive = "no-cache" / extension-pragma

pragma_directive = rf"(?: no-cache | {extension_pragma} )"

#   Pragma = 1#pragma-directive
#
# From RFC 7234, Section 5.4 (RFC 9111 has no ABNF for Pragma). The list uses the sender form;
# RFC 7234's collected ABNF also allows empty list elements, as recipients must accept.

Pragma = list_rule(pragma_directive, 1)

# The warn-* and warning-value rules, and Warning, are RFC 7234's (Section 5.5 and Appendix C);
# RFC 9111 obsoletes Warning and has no ABNF for it.

#   warn-code = 3DIGIT

warn_code = rf"{DIGIT}{{3}}"

#   warn-agent = ( uri-host [ ":" port ] ) / pseudonym

warn_agent = rf"(?: (?: {uri_host} (?: : {port} )? ) | {pseudonym} )"

#   warn-text = quoted-string

warn_text = quoted_string

#   warn-date = DQUOTE HTTP-date DQUOTE

warn_date = rf"(?: {DQUOTE} {HTTP_date} {DQUOTE} )"

#   warning-value = warn-code SP warn-agent SP warn-text [ SP warn-date ]

warning_value = rf"(?: {warn_code} {SP} {warn_agent} {SP} {warn_text} (?: {SP} {warn_date} )? )"

#   Warning = 1#warning-value
#
# The list uses the sender form; see Pragma.

Warning_ = list_rule(warning_value, 1)
