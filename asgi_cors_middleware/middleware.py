"""
Adds the following features to an ASGI app:
    * CORS middleware
"""

import functools
import re
import typing

from asgiref.compatibility import guarantee_single_callable
from starlette.datastructures import Headers, MutableHeaders

from starlette.responses import PlainTextResponse
from starlette.responses import Response

# OPTIONS doesn't make sense to return as an allowed method for CORS.
# See https://stackoverflow.com/a/68529748
ALL_METHODS = ("DELETE", "GET", "PATCH", "POST", "PUT")
SAFELISTED_HEADERS = {
    "Accept", "Accept-Language", "Content-Language", "Content-Type"
}


class CorsASGIApp:
    def __init__(
        self,
        app,
        origins: typing.Sequence[str] = (),
        allow_methods: typing.Sequence[str] = ("GET",),
        allow_headers: typing.Sequence[str] = (),
        allow_credentials: bool = False,
        allow_origin_regex: str = None,
        expose_headers: typing.Sequence[str] = (),
        max_age: int = 600,
    ) -> None:

        if "*" in allow_methods:
            allow_methods = ALL_METHODS

        compiled_allow_origin_regex = None
        if allow_origin_regex is not None:
            compiled_allow_origin_regex = re.compile(allow_origin_regex)

        simple_headers = {}
        if "*" in origins:
            simple_headers["Access-Control-Allow-Origin"] = "*"
        if allow_credentials:
            simple_headers["Access-Control-Allow-Credentials"] = "true"
        if expose_headers:
            simple_headers["Access-Control-Expose-Headers"] = \
                ", ".join(expose_headers)

        preflight_headers = {}
        if "*" in origins:
            preflight_headers["Access-Control-Allow-Origin"] = "*"
        elif len(origins) > 1 or compiled_allow_origin_regex is not None:
            preflight_headers["Vary"] = "Origin"
        preflight_headers.update(
            {
                "Access-Control-Allow-Methods": ", ".join(allow_methods),
                "Access-Control-Max-Age": str(max_age),
            }
        )
        # re-including normally safelisted headers implies that you want to lift the browsers
        #  additional restrictions on those headers. we don't want to do that by default.
        # See https://developer.mozilla.org/en-US/docs/Glossary/CORS-safelisted_request_header#additional_restrictions
        allow_headers = sorted(set(allow_headers))
        if allow_headers and "*" not in allow_headers:
            preflight_headers["Access-Control-Allow-Headers"] = \
                ", ".join(allow_headers)
        if allow_credentials:
            preflight_headers["Access-Control-Allow-Credentials"] = "true"

        self.app = guarantee_single_callable(app)
        self.origins = origins
        self.allow_methods = allow_methods
        self.allow_headers = [h.lower() for h in allow_headers]
        self.allow_all_origins = "*" in origins
        self.allow_all_headers = "*" in allow_headers
        self.allow_origin_regex = compiled_allow_origin_regex
        self.simple_headers = simple_headers
        self.preflight_headers = preflight_headers

    async def __call__(
            self, scope, receive, send
    ) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        method = scope["method"]
        headers = Headers(scope=scope)
        origin = headers.get("origin")

        if origin is None:
            return await self.app(scope, receive, send)

        if method == "OPTIONS":
            if "access-control-request-method" in headers:
                response = self.preflight_response(request_headers=headers)
                await response(scope, receive, send)
                return
            # if this is an options request but was not a cors preflight,
            #  we should skip the simple response processing.
            return await self.app(scope, receive, send)

        await self.simple_response(
            scope, receive, send, request_headers=headers
        )

    def is_allowed_origin(self, origin: str) -> bool:
        if self.allow_all_origins:
            return True

        if self.allow_origin_regex is not None and \
                self.allow_origin_regex.fullmatch(origin):
            return True

        return any(host in origin for host in self.origins)

    def preflight_response(self, request_headers) -> Response:
        requested_origin = request_headers["origin"]
        requested_method = request_headers["access-control-request-method"]
        requested_headers = request_headers.get(
            "access-control-request-headers"
        )

        headers = dict(self.preflight_headers)
        failures = []

        if self.is_allowed_origin(origin=requested_origin):
            if not self.allow_all_origins:
                headers["Access-Control-Allow-Origin"] = requested_origin
        else:
            failures.append("origin")

        if requested_method not in self.allow_methods:
            failures.append("method")

        if self.allow_all_headers and requested_headers is not None:
            headers["Access-Control-Allow-Headers"] = requested_headers
        elif requested_headers is not None:
            for header in [h.lower() for h in requested_headers.split(",")]:
                requested_header = header.strip()
                if requested_header not in self.allow_headers and requested_method not in SAFELISTED_HEADERS:
                    failures.append("headers")

        if failures:
            failure_text = "Disallowed CORS " + ", ".join(failures)
            return PlainTextResponse(
                failure_text, status_code=403, headers=headers
            )

        return Response("", status_code=204, headers=headers)

    async def simple_response(
            self,
            scope,
            receive,
            send,
            request_headers
    ) -> None:
        send = functools.partial(
            self.send, send=send, request_headers=request_headers
        )
        return await self.app(scope, receive, send)

    async def send(self, message, send, request_headers) -> None:
        if message["type"] != "http.response.start":
            await send(message)
            return

        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)
        headers.update(self.simple_headers)
        origin = request_headers["Origin"]
        has_cookie = "cookie" in request_headers

        if self.allow_all_origins and has_cookie:
            headers["Access-Control-Allow-Origin"] = origin

        elif not self.allow_all_origins and \
                self.is_allowed_origin(origin=origin):
            headers["Access-Control-Allow-Origin"] = origin
            if len(self.origins) > 1 or self.allow_origin_regex is not None:
                headers.add_vary_header("Origin")
        await send(message)
