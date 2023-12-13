# pylint: disable=too-many-branches,too-many-statements

from typing import TYPE_CHECKING, cast

from httplint.note import Note, categories, levels
from httplint.util import relative_time

if TYPE_CHECKING:
    from httplint.message import HttpRequestLinter, HttpResponseLinter


### configuration
CACHEABLE_METHODS = ["GET"]
HEURISTIC_CACHEABLE_STATUS = [200, 203, 206, 300, 301, 410]


class ResponseCacheChecker:
    def __init__(self, response: "HttpResponseLinter") -> None:
        self._response = response
        self._request = cast("HttpRequestLinter", response.related)
        self.notes = response.notes
        self.age: int = 0
        self.store_private = True
        self.freshness_lifetime_private: int = 0
        self.store_shared = True
        self.freshness_lifetime_shared: int = 0

        self.age_value = response.headers.parsed.get("age", 0)
        self.date_value = response.headers.parsed.get("date", None)
        self.expires_value = response.headers.parsed.get("expires", None)
        self.lm_value = response.headers.parsed.get("last-modified", None)
        self.etag_value = response.headers.parsed.get("etag", None)
        self.vary_value = response.headers.parsed.get("vary", set())
        self.cc_value = response.headers.parsed.get("cache-control", [])
        self.cc_dict = dict(self.cc_value)

        if self._request:
            self.request_time = self._request.start_time
        else:
            self.request_time = None
        self.response_time = response.start_time

        if not self.check_basic():
            return
        if not self.check_cache_control():
            return
        if not self.check_age():
            return
        if not self.check_freshness():
            return

    def check_basic(self) -> bool:
        # Is method cacheable?
        if (
            self._request
            and self._request.method
            and self._request.method not in CACHEABLE_METHODS
        ):
            self.store_shared = self.store_private = False
            self._request.notes.add(
                "method", METHOD_UNCACHEABLE, method=self._request.method
            )
            return False

        # Is Vary: * present?
        if "*" in self.vary_value:
            self.store_shared = self.store_private = False
            return False

        # is Date present?
        text_fieldnames = [fn.lower() for (fn, fv) in self._response.headers.text]
        if "date" not in text_fieldnames:
            self.notes.add("", DATE_CLOCKLESS)
            if "expires" in text_fieldnames or "last-modified" in text_fieldnames:
                self.notes.add(
                    "header-expires header-last-modified", DATE_CLOCKLESS_BAD_HDR
                )

        return True

    def check_cache_control(self) -> bool:
        if "no-store" in self.cc_dict:
            self.store_shared = self.store_private = False
            self.notes.add("header-cache-control", NO_STORE)
            return False

        if "private" in self.cc_dict:
            self.store_shared = False
            self.notes.add("header-cache-control", PRIVATE_CC)

            if "public" in self.cc_dict:
                self.notes.add("header-cache-control", PRIVATE_PUBLIC_CONFLICT)

        elif self._request and "authorization" in [
            k.lower() for k, v in self._request.headers.text
        ]:
            if "public" in self.cc_dict:
                self.notes.add("header-cache-control", PUBLIC_AUTH)
            else:
                self.store_shared = False
                self.notes.add("header-cache-control", PRIVATE_AUTH)
        else:
            self.notes.add("header-cache-control", STORABLE)

            if "public" in self.cc_dict:
                self.notes.add("header-cache-control", PUBLIC_UNNECESSARY)

        # no-cache?
        if "no-cache" in self.cc_dict:
            if self.lm_value is None and self.etag_value is None:
                self.notes.add("header-cache-control", NO_CACHE_NO_VALIDATOR)
            else:
                self.notes.add("header-cache-control", NO_CACHE)

        return True

    def check_age(self) -> bool:
        if self.response_time and self.date_value and self.date_value > 0:
            apparent_age = max(0, int(self.response_time) - self.date_value)
        else:
            apparent_age = 0

        if self.request_time and self.response_time:
            response_delay = self.response_time - self.request_time
            corrected_age_value = self.age_value + response_delay
        else:
            corrected_age_value = self.age_value

        corrected_initial_age = max(apparent_age, corrected_age_value)
        self.age = corrected_initial_age

        if self.age >= 1:
            age_str = relative_time(self.age, 0, 0)
            self.notes.add("header-age header-date", CURRENT_AGE, age=age_str)
        return True

    def check_freshness(self) -> bool:
        expires_hdr_present = "expires" in [
            n.lower() for (n, v) in self._response.headers.text
        ]
        has_explicit_freshness = False
        has_cc_freshness = False
        freshness_hdrs = ["header-date"]
        if "max-age" in self.cc_dict:
            self.freshness_lifetime_private = self.cc_dict["max-age"]
            self.freshness_lifetime_shared = self.cc_dict["max-age"]
            freshness_hdrs.append("header-cache-control")
            has_explicit_freshness = True
            has_cc_freshness = True
        if "s-maxage" in self.cc_dict:
            self.freshness_lifetime_shared = self.cc_dict["s-maxage"]
            freshness_hdrs.append("header-cache-control")
            has_explicit_freshness = True
            has_cc_freshness = True
        if expires_hdr_present and self.response_time:
            # An invalid Expires header means it's automatically stale
            has_explicit_freshness = True
            freshness_hdrs.append("header-expires")
            expires_lifetime = self.freshness_lifetime_shared = (
                self.expires_value or 0
            ) - (self.date_value or int(self.response_time))
            if not self.freshness_lifetime_private:
                self.freshness_lifetime_private = expires_lifetime
            if not self.freshness_lifetime_shared:
                self.freshness_lifetime_shared = expires_lifetime

        freshness_left = self.freshness_lifetime_private - self.age
        freshness_left_str = relative_time(abs(int(freshness_left)), 0, 0)
        freshness_lifetime_str = relative_time(
            int(self.freshness_lifetime_private), 0, 0
        )

        fresh = freshness_left > 0
        current_age_str = relative_time(self.age, 0, 0)

        if has_explicit_freshness:
            if fresh:
                self.notes.add(
                    " ".join(freshness_hdrs),
                    FRESHNESS_FRESH,
                    freshness_lifetime=freshness_lifetime_str,
                    freshness_left=freshness_left_str,
                    current_age=current_age_str,
                )
            elif has_cc_freshness and self.age > self.freshness_lifetime_private:
                self.notes.add(
                    " ".join(freshness_hdrs),
                    FRESHNESS_STALE_CACHE,
                    freshness_lifetime=freshness_lifetime_str,
                    freshness_left=freshness_left_str,
                    current_age=current_age_str,
                )
            else:
                self.notes.add(
                    " ".join(freshness_hdrs),
                    FRESHNESS_STALE_ALREADY,
                    freshness_lifetime=freshness_lifetime_str,
                    freshness_left=freshness_left_str,
                    current_age=current_age_str,
                )
        # can heuristic freshness be used?
        elif self._response.status_code in HEURISTIC_CACHEABLE_STATUS:
            self.notes.add("header-last-modified", FRESHNESS_HEURISTIC)
        else:
            self.notes.add("", FRESHNESS_NONE)

        if "must-revalidate" in self.cc_dict:
            if fresh:
                self.notes.add("header-cache-control", FRESH_MUST_REVALIDATE)
            elif has_explicit_freshness:
                self.notes.add("header-cache-control", STALE_MUST_REVALIDATE)
        elif "proxy-revalidate" in self.cc_dict or "s-maxage" in self.cc_dict:
            if fresh:
                self.notes.add("header-cache-control", FRESH_PROXY_REVALIDATE)
            elif has_explicit_freshness:
                self.notes.add("header-cache-control", STALE_PROXY_REVALIDATE)
        else:
            if fresh:
                self.notes.add("header-cache-control", FRESH_SERVABLE)
            elif has_explicit_freshness:
                self.notes.add("header-cache-control", STALE_SERVABLE)

        return True


class METHOD_UNCACHEABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "Responses to the %(method)s method can't be stored by caches."
    _text = """\
"""


class DATE_CLOCKLESS(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "%(message)s doesn't have a Date header."
    _text = """\
Although HTTP allows a server not to send a `Date` header in responses if it doesn't have a local
clock, this can make calculation of a stored response's age inexact."""


class DATE_CLOCKLESS_BAD_HDR(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "%(message)s has an Expires or Last-Modified header, but no Date."
    _text = """\
Because both the `Expires` and `Last-Modified` headers are date-based, it's necessary to send when
the message was generated in `Date` for them to be useful; otherwise, clock drift, transit times
between nodes as well as caching could skew their application."""


class NO_STORE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s can't be stored by caches."
    _text = """\
The `Cache-Control: no-store` directive indicates that this response can't be stored by a cache."""


class PRIVATE_CC(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s only allows private caches to store it."
    _text = """\
The `Cache-Control: private` directive indicates that the response can only be stored by caches
that are specific to a single user; for example, a browser cache. Shared caches, such as those in
proxies, cannot store it."""


class PRIVATE_PUBLIC_CONFLICT(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = (
        "%(message)s contains both the `public` and `private` Cache-Control directives."
    )
    _text = """\
`Cache-Control: public` and `Cache-Control: private` conflict; they should not occur on the same message.

Conservative caches will ignore `public` and honor `private`, but this cannot be relied upon."""


class PRIVATE_AUTH(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s can only be stored by private caches, because the request was \
authenticated."
    _text = """\
Because the request was authenticated and this response doesn't contain a `Cache-Control: public`
directive, this response can only be stored by caches that are specific to a single user; for
example, a browser cache. Shared caches, such as those in proxies, cannot store it."""


class PUBLIC_AUTH(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s can be stored by all caches, even though the request was authenticated."
    _text = """\
Usually, responses to authenticated requests can't be stored by shared caches. However, because
This response contains a `Cache-Control: public` directive, it can be stored by all caches,
including shared caches (like those in proxies)."""


class PUBLIC_UNNECESSARY(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "Cache-Control: public is rarely necessary."
    _text = """\
The `Cache-Control: public` directive makes a response cacheable even when the request had an
`Authorization` header (i.e., HTTP authentication was in use). Therefore, HTTP-authenticated (NOT cookie-authenticated) resources _may_ have reason to use
`public`.

Other responses **do not need to contain `public`**; it does not make the
response "more cacheable", and only makes the response headers larger."""


class STORABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = """\
%(message)s allows all caches to store it."""
    _text = """\
A cache can store this response; it may or may not be able to use it to satisfy a particular
request."""


class NO_CACHE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s cannot be served from cache without validation."
    _text = """\
The `Cache-Control: no-cache` directive means that while caches **can** store this
response, they cannot use it to satisfy a request unless it has been validated (either with an
`If-None-Match` or `If-Modified-Since` conditional) for that request."""


class NO_CACHE_NO_VALIDATOR(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s cannot be served from cache without validation."
    _text = """\
The `Cache-Control: no-cache` directive means that while caches **can** store this response, they
cannot use it to satisfy a request unless it has been validated (either with an `If-None-Match` or
`If-Modified-Since` conditional) for that request.

%(message)s doesn't have a `Last-Modified` or `ETag` header, so it effectively can't be used by a
cache."""


class CURRENT_AGE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s has been cached for %(age)s."
    _text = """\
HTTP defines an algorithm that uses the `Age` header, `Date` header, and local time observations to
determine the age of a response. As a result, caches might use a value other than that in the `Age`
header to determine how old the response is -- and therefore how much longer it can be used."""


class FRESHNESS_FRESH(Note):
    category = categories.CACHING
    level = levels.GOOD
    _summary = "%(message)s is fresh until %(freshness_left)s from now."
    _text = """\
A response can be considered fresh when its age (here, %(current_age)s) is less than its freshness
lifetime (in this case, %(freshness_lifetime)s)."""


class FRESHNESS_STALE_CACHE(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "%(message)s has been served stale by a cache."
    _text = """\
An HTTP response is stale when its age (here, %(current_age)s) is equal to or exceeds its freshness
lifetime (in this case, %(freshness_lifetime)s).

HTTP allows caches to use stale responses to satisfy requests under exceptional circumstances;
e.g., when they lose contact with the origin server. Either that has happened here, or the cache
has ignored the response's freshness directives."""


class FRESHNESS_STALE_ALREADY(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s is already stale."
    _text = """\
A cache considers a HTTP response stale when its age (here, %(current_age)s) is equal to or exceeds
its freshness lifetime (in this case, %(freshness_lifetime)s).

HTTP allows caches to use stale responses to satisfy requests only under exceptional circumstances;
e.g., when they lose contact with the origin server."""


class FRESHNESS_HEURISTIC(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = (
        "%(message)s allows caches to assign their own freshness lifetimes to it."
    )
    _text = """\
When responses with certain status codes don't have explicit freshness information (like a `
Cache-Control: max-age` directive, or `Expires` header), caches are allowed to estimate how fresh
it is using a heuristic.

Usually, but not always, this is done using the `Last-Modified` header. For example, if your
response was last modified a week ago, a cache might decide to consider the response fresh for a
day.

Consider adding a `Cache-Control` header; otherwise, it may be cached for longer or shorter than
you'd like."""


class FRESHNESS_NONE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = (
        "%(message)s can only be served by a cache under exceptional circumstances."
    )
    _text = """\
%(message)s doesn't have explicit freshness information (like a ` Cache-Control: max-age`
directive, or `Expires` header), and this status code doesn't allow caches to calculate their own.

Therefore, while caches may be allowed to store it, they can't use it, except in unusual
circumstances, such a when the origin server can't be contacted.

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive.

Note that many caches will not store the response at all, because it is not generally useful to do
so."""


class FRESH_SERVABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s can be served when stale by a cache under exceptional circumstances."
    _text = """\
HTTP allows stale responses to be served under some circumstances; for example, if the origin
server can't be contacted, a stale response can be used (even if it doesn't have explicit freshness
information).

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive."""


class STALE_SERVABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s is stale and can be served by a cache under exceptional circumstances."
    _text = """\
HTTP allows stale responses to be served under some circumstances; for example, if the origin
server can't be contacted, a stale response can be used (even if it doesn't have explicit freshness
information).

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive."""


class FRESH_MUST_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s cannot be served by a cache once it becomes stale."
    _text = """\
The `Cache-Control: must-revalidate` directive forbids caches from using stale responses to satisfy
requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response."""


class STALE_MUST_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s cannot be served by a cache, because it is stale."
    _text = """\
The `Cache-Control: must-revalidate` directive forbids caches from using stale responses to satisfy
requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response."""


class FRESH_PROXY_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s cannot be served by a shared cache once it becomes stale."
    _text = """\
The presence of the `Cache-Control: proxy-revalidate` and/or `s-maxage` directives forbids shared
caches (e.g., proxy caches) from using stale responses to satisfy requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response.

These directives do not affect private caches; for example, those in browsers."""


class STALE_PROXY_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s cannot be served by a shared cache, because it is stale."
    _text = """\
The presence of the `Cache-Control: proxy-revalidate` and/or `s-maxage` directives forbids shared
caches (e.g., proxy caches) from using stale responses to satisfy requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response.

These directives do not affect private caches; for example, those in browsers."""
