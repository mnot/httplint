"""
Regex for RFC9651

These regex are directly derived from the ABNF in RFC9651, Appendix C (which obsoletes
RFC 8941).

    <https://www.rfc-editor.org/rfc/rfc9651.html#appendix-C>

That ABNF is non-normative and "cannot be used to validate" Structured Field syntax on its own:
the parsing algorithms in Section 4.2 take precedence.

They should be processed with re.VERBOSE.

The alternatives are in the RFC's order (e.g., sf-integer before sf-decimal, and parameters
before "=" member-value). That doesn't change what a whole-string match (re.fullmatch)
accepts, but an unanchored match (re.match) can return a shorter match than a longest-first
order would: sf_item on "1.5;a=1" matches "1", and sf_dictionary on "a=1, b" matches "a".
Anchor these rules, or follow them with the context that has to come next.
"""

# pylint: disable=invalid-name

from .rfc5234 import ALPHA, DIGIT, DQUOTE, SP
from .rfc9110 import OWS

# lcalpha = %x61-7A ; a-z
#
# The %x values in the ABNF are case-sensitive, so these are wrapped in (?-i: ... ) against
# the re.IGNORECASE that fields are matched with.

lcalpha = r"(?-i:[a-z])"

# lc-hexdig = DIGIT / %x61-66 ; 0-9, a-f

lc_hexdig = rf"(?: {DIGIT} | (?-i:[a-f]) )"

# pct-encoded = "%" lc-hexdig lc-hexdig

pct_encoded = rf"(?: % {lc_hexdig} {lc_hexdig} )"

# unescaped = %x20-21 / %x23-24 / %x26-5B / %x5D-7E

unescaped = r"[\x20-\x21\x23-\x24\x26-\x5B\x5D-\x7E]"

# bs-escaped = "\" ( DQUOTE / "\" )

bs_escaped = rf"(?: \\ (?: {DQUOTE} | \\ ) )"

# base64 = *( ALPHA / DIGIT / "+" / "/" ) *"="

base64 = rf"(?: (?: {ALPHA} | {DIGIT} | \+ | / )* =* )"

# sf-integer = ["-"] 1*15DIGIT

sf_integer = rf"(?: -? {DIGIT}{{1,15}} )"

# sf-decimal = ["-"] 1*12DIGIT "." 1*3DIGIT

sf_decimal = rf"(?: -? {DIGIT}{{1,12}} \. {DIGIT}{{1,3}} )"

# sf-string = DQUOTE *( unescaped / "%" / bs-escaped ) DQUOTE

sf_string = rf"(?: {DQUOTE} (?: {unescaped} | % | {bs_escaped} )* {DQUOTE} )"

# sf-token = ( ALPHA / "*" ) *( tchar / ":" / "/" )
# tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "." /
#         "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA
#
# Written with character classes rather than the alternations of rfc9110.tchar, which are slow
# to match one character at a time; they accept the same characters.

sf_token = r"(?: [a-zA-Z*] [a-zA-Z0-9!#$%&'*+\-.^_`|~:/]* )"

# sf-binary = ":" base64 ":"

sf_binary = rf"(?: : {base64} : )"

# sf-boolean = "?" ( "0" / "1" )

sf_boolean = r"(?: \? [01] )"

# sf-date = "@" sf-integer

sf_date = rf"(?: @ {sf_integer} )"

# sf-displaystring = "%" DQUOTE *( unescaped / "\" / pct-encoded ) DQUOTE

sf_displaystring = rf"(?: % {DQUOTE} (?: {unescaped} | \\ | {pct_encoded} )* {DQUOTE} )"

# bare-item = sf-integer / sf-decimal / sf-string / sf-token
#             / sf-binary / sf-boolean / sf-date / sf-displaystring

bare_item = (
    rf"(?: {sf_integer} | {sf_decimal} | {sf_string} | {sf_token}"
    rf" | {sf_binary} | {sf_boolean} | {sf_date} | {sf_displaystring} )"
)

# key = ( lcalpha / "*" )
#       *( lcalpha / DIGIT / "_" / "-" / "." / "*" )

key = rf"(?: (?: {lcalpha} | \* ) (?: {lcalpha} | {DIGIT} | _ | \- | \. | \* )* )"

# param-key = key

param_key = key

# param-value = bare-item

param_value = bare_item

# parameter = param-key [ "=" param-value ]

parameter = rf"(?: {param_key} (?: = {param_value} )? )"

# parameters = *( ";" *SP parameter )

parameters = rf"(?: (?: ; {SP}* {parameter} )* )"

# sf-item = bare-item parameters

sf_item = rf"(?: {bare_item} {parameters} )"

# inner-list = "(" *SP [ sf-item *( 1*SP sf-item ) *SP ] ")"
#              parameters

inner_list = rf"(?: \( {SP}* (?: {sf_item} (?: {SP}+ {sf_item} )* {SP}* )? \) {parameters} )"

# list-member = sf-item / inner-list

list_member = rf"(?: {sf_item} | {inner_list} )"

# sf-list = list-member *( OWS "," OWS list-member )

sf_list = rf"(?: {list_member} (?: {OWS} , {OWS} {list_member} )* )"

# member-key = key

member_key = key

# member-value = sf-item / inner-list

member_value = list_member

# dict-member = member-key ( parameters / ( "=" member-value ))

dict_member = rf"(?: {member_key} (?: {parameters} | = {member_value} ) )"

# sf-dictionary = dict-member *( OWS "," OWS dict-member )

sf_dictionary = rf"(?: {dict_member} (?: {OWS} , {OWS} {dict_member} )* )"

# Not in the ABNF: a union of the three top-level types, for convenience. A field defines which
# one it uses.

sf_value = rf"(?: {sf_dictionary} | {sf_list} | {sf_item} )"
