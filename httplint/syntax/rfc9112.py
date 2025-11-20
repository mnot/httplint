"""
Regex for RFC9112
"""

# pylint: disable=invalid-name, line-too-long

from .rfc5234 import (
    CRLF,
    DIGIT,
    HEXDIG,
    OCTET,
    SP,
    VCHAR,
    HTAB,
)
from .rfc3986 import (
    absolute_URI,
    authority,
    query,
    segment,
)
from .rfc9110 import (
    OWS,
    BWS,
    token,
    quoted_string,
    list_rule,
    field_name,
    field_value,
)

SPEC_URL = "http://httpwg.org/specs/rfc9112"

#   header-field = field-name ":" OWS field-value OWS

header_field = rf"(?: {field_name} : {OWS} {field_value} {OWS} )"

## Chunked Encoding

#   chunk-size = 1*HEXDIG

chunk_size = rf"(?: {HEXDIG}+ )"

#   chunk-ext-name = token

chunk_ext_name = token

#   chunk-ext-val = token / quoted-string

chunk_ext_val = rf"(?: {token} | {quoted_string} )"

#   chunk-ext = *( ";" chunk-ext-name [ "=" chunk-ext-val ] )

chunk_ext = rf"(?: \; {chunk_ext_name} (?: \= {chunk_ext_val} )? )"

#   chunk-data = 1*OCTET

chunk_data = rf"{OCTET}+"

#   chunk = chunk-size [ chunk-ext ] CRLF chunk-data CRLF

chunk = rf"(?: {chunk_size} (?: {chunk_ext} )? {CRLF} {chunk_data} {CRLF} )"

#   last-chunk = 1*"0" [ chunk-ext ] CRLF

last_chunk = rf"(?: (?: 0 )+ (?: {chunk_ext} )? {CRLF} )"

#   trailer-part = *( header-field CRLF )

trailer_part = rf"(?: {header_field} {CRLF} )*"

#   chunked-body = *chunk last-chunk trailer-part CRLF

chunked_body = rf"(?: (?: chunk )* {last_chunk} {trailer_part} {CRLF} )"


## Transfer-Encoding

#   transfer-parameter = token BWS "=" BWS ( token / quoted-string )

transfer_parameter = rf"(?: {token} {BWS} = {BWS} (?: {token} | {quoted_string} ) )"

#   transfer-extension = token *( OWS ";" OWS transfer-parameter )

transfer_extension = rf"(?: {token} (?: {OWS} ; {OWS} {transfer_parameter} )* )"

#   transfer-coding = "chunked" / "compress" / "deflate" / "gzip" / transfer-extension

transfer_coding = rf"(?: chunked | compress | deflate | gzip | {transfer_extension} )"

#   Transfer-Encoding = [ transfer-coding *( OWS "," OWS transfer-coding ) ]

Transfer_Encoding = list_rule(transfer_coding, 1)

## Message

#   HTTP-name = %x48.54.54.50 ; HTTP

HTTP_name = r"HTTP"

#   HTTP-version = HTTP-name "/" DIGIT "." DIGIT

HTTP_version = rf"{HTTP_name} / {DIGIT} . {DIGIT}"

#   method = token

method = token

#   absolute-form = absolute-URI

absolute_form = absolute_URI

#   absolute-path = 1*( "/" segment )

absolute_path = rf"(?: / {segment} )+"

#   asterisk-form = "*"

asterisk_form = r"\*"

#   authority-form = authority

authority_form = authority

#   origin-form = absolute-path [ "?" query ]

origin_form = rf"(?: {absolute_path} (?: {query} )? )"

#   request-target = origin-form / absolute-form / authority-form / asterisk-form

request_target = (
    rf"(?: {origin_form} | {absolute_form} | {authority_form} | {asterisk_form} )"
)

#   request-line = method SP request-target SP HTTP-version CRLF

request_line = rf"(?: {method} [ ] {request_target} [ ] {HTTP_version} {CRLF} )"

#   status-code = 3DIGIT

status_code = rf"(?: {DIGIT}{{3}} )"

#   obs-text = %x80-FF
obs_text = r"[\x80-\xff]"

#   reason-phrase = *( HTAB / SP / VCHAR / obs-text )

reason_phrase = rf"(?: {HTAB} | {SP} | {VCHAR} | {obs_text} )*"

#   status-line = HTTP-version SP status-code SP reason-phrase CRLF

status_line = rf"(?: {HTTP_version} [ ] {status_code} [ ] {reason_phrase} {CRLF} )"

#   start-line = request-line / status-line

start_line = rf"(?: {request_line} | {status_line} )"

#   message-body = *OCTET

message_body = rf"(?: {OCTET}* )"

#   HTTP-message = start-line *( header-field CRLF ) CRLF [ message-body ]

HTTP_message = (
    rf"(?: {start_line} (?: {header_field} {CRLF} )* {CRLF} (?: {message_body} )? )"
)
