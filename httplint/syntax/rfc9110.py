"""
Regex for RFC9110
"""

# pylint: disable=invalid-name, line-too-long

from typing import Optional

from .rfc5234 import (
    ALPHA,
    DIGIT,
    DQUOTE,
    HTAB,
    SP,
    VCHAR,
)
from .rfc3986 import (
    URI_reference,
    absolute_URI,
    authority,
    path_abempty,
    port,
    query,
    relative_part,
    segment,
    host as uri_host,
)
from .rfc5646 import Language_Tag
from .rfc5322 import mailbox

SPEC_URL = "http://httpwg.org/specs/rfc9110"


#   OWS = *( SP / HTAB )

OWS = rf"(?: {SP} | {HTAB} )*"

#   BWS = OWS

BWS = OWS

#   RWS = 1*( SP / HTAB )

RWS = rf"(?: {SP} | {HTAB} )+"

#   obs-text = %x80-FF

obs_text = r"[\x80-\xff]"

#   tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "."
#           / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA

tchar = rf"(?: ! | \# | \$ | % | & | ' | \* | \+ | \- | \. | \^ | _ | ` | \| | \~ | {DIGIT} | {ALPHA} )"

#   token = 1*tchar

token = rf"{tchar}+"

#   qdtext = HTAB / SP / "!" / %x23-5B ; '#'-'['
#    / %x5D-7E ; ']'-'~'
#    / obs-text

qdtext = r"[\t !\x23-\x5b\x5d-\x7e\x80-\xff]"

#   quoted-pair = "\" ( HTAB / SP / VCHAR / obs-text )

quoted_pair = rf"(?: \\ (?: {HTAB} | {SP} | {VCHAR} | {obs_text} ) )"

#   quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE

quoted_string = rf"(?: \" (?: {qdtext} | {quoted_pair} )* \" )"


class list_rule:
    """
    Given a piece of ABNF, wrap it in the "list rule"
    as per RFC 9110, Section 5.6.1.

    <https://www.rfc-editor.org/rfc/rfc9110.html#section-5.6.1>

    Uses the sender syntax, not the more lenient recipient syntax.
    """

    def __init__(self, element: str, minimum: Optional[int] = None) -> None:
        self.element = element
        self.minimum = minimum

    def __str__(self) -> str:
        if self.minimum and self.minimum == 1:
            # 1#element => element *( OWS "," OWS element )
            return r"(?: {element} (?: {OWS} , {OWS} {element} )* )".format(
                element=self.element, OWS=OWS
            )
        if self.minimum and self.minimum > 1:
            # <n>#<m>element => element <n-1>*<m-1>( OWS "," OWS element )
            adj_min = self.minimum - 1
            return (
                r"(?: {element} (?: {OWS} , {OWS} {element} ){{{adj_min},}} )".format(
                    element=self.element, OWS=OWS, adj_min=adj_min
                )
            )
        # element => [ 1#element ]
        return r"(?: {element} (?: {OWS} , {OWS} {element} )* )?".format(
            element=self.element, OWS=OWS
        )


#   parameter-name = token

parameter_name = token

#   parameter-value = ( token / quoted-string )

parameter_value = rf"(?: {token} | {quoted_string} )"

#   parameter = parameter-name "=" parameter-value

parameter = rf"(?: {parameter_name} = {parameter_value} )"

#   parameters = *( OWS ";" OWS [ parameter ] )

parameters = rf"(?: {OWS} ; {OWS} {parameter}? )*"

#   qvalue = ( "0" [ "." *3DIGIT ] ) / ( "1" [ "." *3"0" ] )

qvalue = rf"(?: (?: 0 (?: \. {DIGIT}{{,3}} ) ) | (?: 1 (?: \. [0]{{,3}} ) ) )"

#   weight = OWS ";" OWS "q=" qvalue

weight = rf"(?: {OWS} \; {OWS} q\= {qvalue} )"

#   type = token

_type = token

#   subtype = token

subtype = token

#   media-type = type "/" subtype parameters

media_type = rf"(?: {_type} / {subtype} {parameters} )"

#   media-range = ( "*/*" / ( type "/*" ) / ( type "/" subtype ) ) parameters

media_range = (
    rf"(?: (?: \*/\* | (?: {_type} /\* ) | (?: {_type} / {subtype} ) ) {parameters} )"
)

#   Accept = [ ( media-range [ weight ] ) *( OWS "," OWS ( media-range [ weight ] ) ) ]

Accept = list_rule(rf"(?: {media_range} (?: {weight} )? )")

#   Accept-Charset = [ ( ( token / "*" ) [ weight ] )
#                      *( OWS "," OWS ( ( token / "*" ) [ weight ] ) ) ]

Accept_Charset = list_rule(rf"(?: (?: {token} | \* ) {weight}? )")

#   content-coding = token

content_coding = token

#   codings = content-coding / "identity" / "*"

codings = rf"(?: {content_coding} | identity | \* )"

#   Accept-Encoding = [ ( codings [ weight ] ) *( OWS "," OWS ( codings [ weight ] ) ) ]

Accept_Encoding = list_rule(rf"(?: {codings} {weight}? )")

#   language-range = <language-range, see [RFC4647], Section 2.1>

language_range = (
    rf"(?: (?: {ALPHA}{{1,8}} (?: \- (?: {ALPHA} {DIGIT} ){{1,8}} )* ) | \* )"
)

#   Accept-Language = [ ( language-range [ weight ] )
#                       *( OWS "," OWS ( language-range [ weight ] ) ) ]

Accept_Language = list_rule(rf"(?: {language_range} {weight}? )")

#   range-unit = token

range_unit = token

#   acceptable-ranges = range-unit *( OWS "," OWS range-unit )

acceptable_ranges = list_rule(range_unit, 1)

#   Accept-Ranges = acceptable-ranges

Accept_Ranges = acceptable_ranges

#   method = token

method = token

#   Allow = [ method *( OWS "," OWS method ) ]

Allow = list_rule(method)

#   auth-scheme = token

auth_scheme = token

#   auth-param = token BWS "=" BWS ( token / quoted-string )

auth_param = rf"(?: {token} {BWS} = {BWS} (?: {token} | {quoted_string} ) )"

#   Authentication-Info = [ auth-param *( OWS "," OWS auth-param ) ]

Authentication_Info = list_rule(auth_param)

#   token68 = 1*( ALPHA / DIGIT / "-" / "." / "_" / "~" / "+" / "/" ) *"="

token68 = rf"(?: (?: {ALPHA} | {DIGIT} | \- | \. | _ | \~ | \+ | / )+ =* )"

#   credentials = auth-scheme [ 1*SP ( token68 / [ auth-param *( OWS "," OWS auth-param ) ] ) ]

credentials = rf"""(?: {auth_scheme}
                        (?: {SP}+
                            (?: {token68} |
                                (?:
                                    (?: , | {auth_param} )
                                    (?: {OWS} , (?: {OWS} {auth_param} )? )*
                                )?
                            )
                        )?
)"""

#   Authorization = credentials

Authorization = credentials

#   connection-option = token

connection_option = token

#   Connection = [ connection-option *( OWS "," OWS connection-option ) ]

Connection = list_rule(connection_option)

#   Content-Encoding = [ content-coding *( OWS "," OWS content-coding ) ]

Content_Encoding = list_rule(content_coding)

#   language-tag = <Language-Tag, see [RFC5646], Section 2.1>

language_tag = Language_Tag

#   Content-Language = [ language-tag *( OWS "," OWS language-tag ) ]

Content_Language = list_rule(language_tag)

#   Content-Length = 1*DIGIT

Content_Length = rf"{DIGIT}+"

#   absolute-URI = <absolute-URI, see [URI], Section 4.3>

#   relative-part = <relative-part, see [URI], Section 4.2>

#   query = <query, see [URI], Section 3.4>

#   partial-URI = relative-part [ "?" query ]

partial_URI = rf"(?: {relative_part} (?: {query} )? )"

#   Content-Location = absolute-URI / partial-URI

Content_Location = rf"(?: {absolute_URI} | {partial_URI} )"

#   first-pos = 1*DIGIT

first_pos = rf"{DIGIT}+"

#   last-pos = 1*DIGIT

last_pos = rf"{DIGIT}+"

#   incl-range = first-pos "-" last-pos

incl_range = rf"(?: {first_pos} \- {last_pos} )"

#   complete-length = 1*DIGIT

complete_length = rf"{DIGIT}+"

#   range-resp = incl-range "/" ( complete-length / "*" )

range_resp = rf"(?: {incl_range} / (?: {complete_length} | \* ) )"

#   unsatisfied-range = "*/" complete-length

unsatisfied_range = rf"(?: \*/ {complete_length} )"

#   Content-Range = range-unit SP ( range-resp / unsatisfied-range )

Content_Range = rf"(?: {range_unit} {SP} (?: {range_resp} | {unsatisfied_range} ) )"

#   Content-Type = media-type

Content_Type = media_type

#   day = 2DIGIT

day = rf"(?: {DIGIT} {DIGIT} )"

#   day-name = %x4D.6F.6E ; Mon
#    / %x54.75.65 ; Tue
#    / %x57.65.64 ; Wed
#    / %x54.68.75 ; Thu
#    / %x46.72.69 ; Fri
#    / %x53.61.74 ; Sat
#    / %x53.75.6E ; Sun

day_name = r"(?: Mon | Tue | Wed | Thu | Fri | Sat | Sun )"

#   month = %x4A.61.6E ; Jan
#    / %x46.65.62 ; Feb
#    / %x4D.61.72 ; Mar
#    / %x41.70.72 ; Apr
#    / %x4D.61.79 ; May
#    / %x4A.75.6E ; Jun
#    / %x4A.75.6C ; Jul
#    / %x41.75.67 ; Aug
#    / %x53.65.70 ; Sep
#    / %x4F.63.74 ; Oct
#    / %x4E.6F.76 ; Nov
#    / %x44.65.63 ; Dec

month = r"(?: Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec )"

#   year = 4DIGIT

year = rf"(?: {DIGIT}{{4}} )"

#   date1 = day SP month SP year

date1 = rf"(?: {day} {SP} {month} {SP} {year} )"

#   hour = 2DIGIT

hour = rf"(?: {DIGIT} {DIGIT} )"

#   minute = 2DIGIT

minute = rf"(?: {DIGIT} {DIGIT} )"

#   second = 2DIGIT

second = rf"(?: {DIGIT} {DIGIT} )"

#   time-of-day = hour ":" minute ":" second

time_of_day = rf"(?: {hour} : {minute} : {second} )"

#   GMT = %x47.4D.54 ; GMT

GMT = r"(?: GMT )"

#   IMF-fixdate = day-name "," SP date1 SP time-of-day SP GMT

IMF_fixdate = rf"(?: {day_name} , {SP} {date1} {SP} {time_of_day} {SP} {GMT} )"

#   day-name-l = %x4D.6F.6E.64.61.79 ; Monday
#    / %x54.75.65.73.64.61.79 ; Tuesday
#    / %x57.65.64.6E.65.73.64.61.79 ; Wednesday
#    / %x54.68.75.72.73.64.61.79 ; Thursday
#    / %x46.72.69.64.61.79 ; Friday
#    / %x53.61.74.75.72.64.61.79 ; Saturday
#    / %x53.75.6E.64.61.79 ; Sunday

day_name_l = (
    r"(?: Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday )"
)

#   date2 = day "-" month "-" 2DIGIT

date2 = rf"(?: {day} \- {month} \- {DIGIT}{{2}} )"

#   rfc850-date = day-name-l "," SP date2 SP time-of-day SP GMT

rfc850_date = rf"(?: {day_name_l} \, {SP} {date2} {SP} {time_of_day} {SP} {GMT} )"

#   date3 = month SP ( 2DIGIT / ( SP DIGIT ) )

date3 = rf"(?: {month} {SP} (?: {DIGIT}{{2}} | (?: {SP} {DIGIT} ) ) )"

#   asctime-date = day-name SP date3 SP time-of-day SP year

asctime_date = rf"(?: {day_name} {SP} {date3} {SP} {time_of_day} {SP} {year} )"

#   obs-date = rfc850-date / asctime-date

obs_date = rf"(?: {rfc850_date} | {asctime_date} )"

#   HTTP-date = IMF-fixdate / obs-date

HTTP_date = rf"(?: {IMF_fixdate} | {obs_date} )"

#   Date = HTTP-date

Date = HTTP_date

#   weak = %x57.2F ; W/

weak = r"(?: \x57\x2F )"

#   etagc = "!" / %x23-7E ; '#'-'~' / obs-text

etagc = rf"(?: ! | [\x23-\x7E] | {obs_text} )"

#   opaque-tag = DQUOTE *etagc DQUOTE

opaque_tag = rf"(?: {DQUOTE} {etagc}* {DQUOTE} )"

#   entity-tag = [ weak ] opaque-tag

entity_tag = rf"(?: {weak}? {opaque_tag} )"

#   ETag = entity-tag

ETag = entity_tag

#   expectation = token [ "=" ( token / quoted-string ) parameters ]

expectation = rf"(?: {token} (?: = (?: {token} | {quoted_string} ) {parameters} )? )"

#   Expect = [ expectation *( OWS "," OWS expectation ) ]

Expect = list_rule(expectation)

#   mailbox = <mailbox, see [RFC5322], Section 3.4>

#   From = mailbox

From = mailbox

#   uri-host = <host, see [URI], Section 3.2.2>

#   Host = uri-host [ ":" port ]

Host = rf"{uri_host} (?: : {port} )?"

#   If-Match = "*" / [ entity-tag *( OWS "," OWS entity-tag ) ]

If_Match = rf"(?: \* | {list_rule(entity_tag)} )"

#   If-Modified-Since = HTTP-date

If_Modified_Since = HTTP_date

#   If-None-Match = "*" / [ entity-tag *( OWS "," OWS entity-tag ) ]

If_None_Match = rf"(?: \* | {list_rule(entity_tag)} )"

#   If-Range = entity-tag / HTTP-date

If_Range = rf"(?: {entity_tag} | {HTTP_date} )"

#   If-Unmodified-Since = HTTP-date

If_Unmodified_Since = HTTP_date

#   Last-Modified = HTTP-date

Last_Modified = HTTP_date

#   URI-reference = <URI-reference, see [URI], Section 4.1>

#   Location = URI-reference

Location = URI_reference

#   Max-Forwards = 1*DIGIT

Max_Forwards = rf"(?: {DIGIT}+ )"

#   challenge = auth-scheme [ 1*SP ( token68 / [ auth-param *( OWS "," OWS auth-param ) ] ) ]

challenge = rf"""(?: {auth_scheme}
                        (?: {SP}+
                            (?: {token68} |
                                (?:
                                    (?: , | {auth_param} )
                                    (?: {OWS} , (?: {OWS} {auth_param} )? )*
                                )?
                            )
                        )?
)"""

#   Proxy-Authenticate = [ challenge *( OWS "," OWS challenge ) ]

Proxy_Authenticate = list_rule(challenge)

#   Proxy-Authentication-Info = [ auth-param *( OWS "," OWS auth-param ) ]

Proxy_Authentication_Info = list_rule(auth_param)

#   Proxy-Authorization = credentials

Proxy_Authorization = credentials

#   int-range = first-pos "-" [ last-pos ]

int_range = rf"(?: {first_pos} \- {last_pos}? )"

#   suffix-length = 1*DIGIT

suffix_length = rf"{DIGIT}+"

#   suffix-range = "-" suffix-length

suffix_range = rf"(?: \- {suffix_length} )"

#   other-range = 1*( %x21-2B ; '!'-'+'
#    / %x2D-7E ; '-'-'~'
#   )

other_range = r"(?: [\x21-\x2B] | [\x2D-\x7E] )+"

#   range-spec = int-range / suffix-range / other-range

range_spec = rf"(?: {int_range} | {suffix_range} | {other_range} )"

#   range-set = range-spec *( OWS "," OWS range-spec )

range_set = list_rule(range_spec, 1)

#   ranges-specifier = range-unit "=" range-set

ranges_specifier = rf"(?: {range_unit} = {range_set} )"

#   Range = ranges-specifier

Range = ranges_specifier

#   Referer = absolute-URI / partial-URI

Referer = rf"(?: {absolute_URI} | {partial_URI} )"

#   delay-seconds = 1*DIGIT

delay_seconds = rf"(?: {DIGIT}+ )"

#   Retry-After = HTTP-date / delay-seconds

Retry_After = rf"(?: {HTTP_date} | {delay_seconds} )"

#   product-version = token

product_version = token

#   product = token [ "/" product-version ]

product = rf"(?: {token} (?: / {product_version} )? )"

#   ctext = HTAB / SP / %x21-27 ; '!'-'''
#   / %x2A-5B ; '*'-'['
#    / %x5D-7E ; ']'-'~'
#    / obs-text

ctext = rf"(?: {HTAB} | {SP} | [\x21-\x27] | [\x2A-\x5b] | [\x5D-\x7E] | {obs_text} )"

#   comment = "(" *( ctext / quoted-pair / comment ) ")"

comment = rf"(?: \( (?: {ctext} | {quoted_pair} )* \) )"

#   Server = product *( RWS ( product / comment ) )

Server = rf"(?: {product} (?: {RWS} (?: {product} | {comment} ) )* )"

#   transfer-parameter = token BWS "=" BWS ( token / quoted-string )

transfer_parameter = rf"(?: {token} {BWS} = {BWS} (?: {token} | {quoted_string} ) )"

#   transfer-coding = token *( OWS ";" OWS transfer-parameter )

transfer_coding = rf"(?: {token} (?: {OWS} ; {OWS} {transfer_parameter} )* )"

#   t-codings = "trailers" / ( transfer-coding [ weight ] )

t_codings = rf"(?: trailers | (?: {transfer_coding} (?: {weight}? ) ) )"

#   TE = [ t-codings *( OWS "," OWS t-codings ) ]

TE = list_rule(t_codings)

#   field-name = token

field_name = token

#   Trailer = [ field-name *( OWS "," OWS field-name ) ]

Trailer = list_rule(field_name)

#   protocol-name = token

protocol_name = token

#   protocol-version = token

protocol_version = token

#   protocol = protocol-name [ "/" protocol-version ]

protocol = rf"(?: {protocol_name} (?: / {protocol_version} )? )"

#   Upgrade = [ protocol *( OWS "," OWS protocol ) ]

Upgrade = list_rule(protocol)

#   User-Agent = product *( RWS ( product / comment ) )

User_Agent = rf"(?: {product} (?: {RWS} (?: {product} | {comment} ) )* )"

#   Vary = [ ( "*" / field-name ) *( OWS "," OWS ( "*" / field-name ) ) ]

Vary = list_rule(rf"(?: \* | {field_name} )")

#   pseudonym = token

pseudonym = token

#   received-protocol = [ protocol-name "/" ] protocol-version

received_protocol = rf"(?: (?: {protocol_name} / )? {protocol_version} )"

#   received-by = pseudonym [ ":" port ]

received_by = rf"(?: (?: {uri_host} (?: : {port} )? ) | {pseudonym} )"

#   Via = [ ( received-protocol RWS received-by [ RWS comment ] )
#           *( OWS "," OWS ( received-protocol RWS received-by [ RWS comment ] ) ) ]

Via = list_rule(
    rf"(?: {received_protocol} {RWS} {received_by} (?: {RWS} {comment} )? )"
)

#   WWW-Authenticate = [ challenge *( OWS "," OWS challenge ) ]

WWW_Authenticate = list_rule(challenge)

#   absolute-path = 1*( "/" segment )

absolute_path = rf"(?: / {segment} )+"

#   authority = <authority, see [URI], Section 3.2>

#   field-vchar = VCHAR / obs-text

field_vchar = rf"(?: {VCHAR} | {obs_text} )"

#   field-content = field-vchar [ 1*( SP / HTAB / field-vchar ) field-vchar ]

field_content = rf"(?: {field_vchar} (?: (?: {SP} | {HTAB} )+ {field_vchar} )? )"

#   field-value = *field-content

field_value = rf"(?: {field_content} )*"

#   http-URI = "http://" authority path-abempty [ "?" query ]

http_URI = rf"(?: http:// {authority} {path_abempty} (?: \? {query} )? )"

#   https-URI = "https://" authority path-abempty [ "?" query ]

https_URI = rf"(?: https:// {authority} {path_abempty} (?: \? {query} )? )"

#   path-abempty = <path-abempty, see [URI], Section 3.3>

#   port = <port, see [URI], Section 3.2.3>
