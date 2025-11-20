"""
Regex for RFC9651

These regex are directly derived from the collected ABNF in RFC9651.

    <https://www.rfc-editor.org/rfc/rfc9651.html#name-collected-abnf>

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name

from .rfc5234 import DIGIT, SP
from .rfc7230 import OWS

# sf-integer = ["-"] 1*15DIGIT
sf_integer = rf"-?{DIGIT}{{1,15}}"

# sf-decimal = ["-"] 1*12DIGIT "." 1*3DIGIT
sf_decimal = rf"-?{DIGIT}{{1,12}}\.{DIGIT}{{1,3}}"

# sf-string = DQUOTE * ( unescaped / "%" / bs-escaped ) DQUOTE
# unescaped = %x20-21 / %x23-24 / %x26-5B / %x5D-7E
# bs-escaped = "\" ( DQUOTE / "\" )
sf_string = r'"(?:[\x20-\x21\x23-\x5B\x5D-\x7E]|(?:\\["\\]))*"'

# sf-token = (ALPHA / "*") *( tchar / ":" / "/" )
# tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "." /
#         "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA
sf_token = r"[a-zA-Z*][a-zA-Z0-9!#$%&'*+\-.^_`|~:/]*"

# sf-binary = ":" *(base64) ":"
# base64 = ALPHA / DIGIT / "+" / "/" / "="
sf_binary = r":[a-zA-Z0-9+/=]*:"

# sf-boolean = "?" ( "0" / "1" )
sf_boolean = r"\?[01]"

# sf-date = "@" sf-integer
sf_date = rf"@{sf_integer}"

# bare-item = sf-integer / sf-decimal / sf-string / sf-token / sf-binary / sf-boolean / sf-date
bare_item = (
    rf"(?:{sf_decimal}|{sf_integer}|{sf_string}|{sf_token}|"
    rf"{sf_binary}|{sf_boolean}|{sf_date})"
)

# key = ( lcalpha / "*" ) *( lcalpha / DIGIT / "_" / "-" / "." / "*" )
# lcalpha = %x61-7A ; a-z
key = r"[a-z*][a-z0-9_\-.*]*"

# param-key = key
param_key = key

# param-value = bare-item
param_value = bare_item

# parameter = ";" *SP param-key [ "=" param-value ]
parameter = rf";{SP}*{param_key}(?:={param_value})?"

# parameters = *parameter
parameters = rf"(?:{parameter})*"

# sf-item = bare-item parameters
sf_item = rf"{bare_item}{parameters}"

# inner-list = "(" *SP [ sf-item *( 1*SP sf-item ) *SP ] ")" parameters
inner_list = rf"\({SP}*(?:{sf_item}(?:{SP}+{sf_item})*{SP}*)?\){parameters}"

# sf-list = list-member *( OWS "," OWS list-member )
# list-member = sf-item / inner_list


list_member = rf"(?:{sf_item}|{inner_list})"
sf_list = rf"{list_member}(?:{OWS},{OWS}{list_member})*"

# sf-dictionary = dict-member *( OWS "," OWS dict-member )
# dict-member = member-key [ "=" member-value ]
# member-key = key
# member-value = sf-item / inner-list
member_key = key
member_value = list_member
dict_member = rf"{member_key}(?:={member_value})?"
sf_dictionary = rf"{dict_member}(?:{OWS},{OWS}{dict_member})*"

# For convenience, a union of all top-level types if needed, though usually headers specify one.
sf_value = rf"(?:{sf_dictionary}|{sf_list}|{sf_item})"
