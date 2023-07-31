import pytest
from asgiref.testing import ApplicationCommunicator as HttpCommunicator
from channels.testing import WebsocketCommunicator

from asgi_cors_middleware.middleware import CorsASGIApp
from .asgi_app import app
from .asgi_app import ASGI2app

REQUEST_METHOD = b"access-control-request-method"
REQUEST_HEADERS = b"access-control-request-headers"
ALLOW_ORIGIN = b"access-control-allow-origin"
ALLOW_METHODS = b"access-control-allow-methods"
ALLOW_HEADERS = b"access-control-allow-headers"
EXPOSE_HEADERS = b"access-control-expose-headers"
MAX_AGE = b"access-control-max-age"


async def do_cors_response(scope, expected_output, cors_options=None, cors_app=None):
    if cors_app is None:
        if cors_options is None:
            cors_options = {}
        cors_app = CorsASGIApp(app=app, **cors_options)
    scope["type"] = "http"
    scope["path"] = "/"
    communicator = HttpCommunicator(
        scope=scope,
        application=cors_app,
    )
    await communicator.send_input({"type": "http.request"})
    response_start = await communicator.receive_output()
    response_body = await communicator.receive_output()
    assert response_start["type"] == "http.response.start"
    assert response_start["status"] == expected_output["status"]
    assert set(response_start["headers"]) == set(expected_output["headers"])
    assert response_body == {
        "type": "http.response.body",
        "body": expected_output["body"],
    }


@pytest.mark.asyncio
class TestOrigins:
    @pytest.mark.parametrize(
        "request_headers, options_origins, expected_headers",
        [
            (
                [(b"origin", b"http://e.com")],
                ["*"],
                [(ALLOW_ORIGIN, b"*")],
            ),
            (
                [(b"origin", b"http://e.com"), (b"cookie", b"session=1234")],
                ["*"],
                [(ALLOW_ORIGIN, b"http://e.com")],
            ),
            (
                [(b"origin", b"http://e.org")],
                ["http://e.edu", "http://e.org"],
                [
                    (ALLOW_ORIGIN, b"http://e.org"),
                    (b"vary", b"Origin"),
                ],
            ),
            (
                [(b"origin", b"http://e.net")],
                ["http://e.net"],
                [(ALLOW_ORIGIN, b"http://e.net")],
            ),
            (
                [(b"origin", b"http://e.com")],
                ["http://e.edu", "http://e.org"],
                [],
            ),
            (
                [(b"origin", b"http://e.com")],
                ["http://e.net"],
                [],
            ),
        ],
        ids=[
            "wildcard",
            "wildcard_cookies",
            "multiple",
            "single",
            "disallowed_multiple",
            "disallowed_single",
        ],
    )
    async def test_simple_response(
        self, request_headers, options_origins, expected_headers
    ):
        await do_cors_response(
            scope={
                "method": "GET",
                "headers": request_headers,
            },
            expected_output={
                "status": 200,
                "headers": expected_headers
                + [
                    (b"content-length", b"17"),
                    (b"content-type", b"application/json"),
                ],
                "body": b'{"hello":"world"}',
            },
            cors_options={"origins": options_origins},
        )

    @pytest.mark.parametrize(
        "from_origin, options_origins, expected_headers, options_status, body",
        [
            (
                b"http://e.com",
                ["*"],
                [(ALLOW_METHODS, b"GET"), (MAX_AGE, b"600"), (ALLOW_ORIGIN, b"*")],
                204,
                b"",
            ),
            (
                b"http://e.org",
                ["http://e.edu", "http://e.org"],
                [
                    (ALLOW_METHODS, b"GET"),
                    (MAX_AGE, b"600"),
                    (ALLOW_ORIGIN, b"http://e.org"),
                    (b"vary", b"Origin"),
                ],
                204,
                b"",
            ),
            (
                b"http://e.net",
                ["http://e.net"],
                [
                    (ALLOW_METHODS, b"GET"),
                    (MAX_AGE, b"600"),
                    (ALLOW_ORIGIN, b"http://e.net"),
                ],
                204,
                b"",
            ),
            (
                b"http://e.com",
                ["http://e.edu", "http://e.org"],
                [
                    (ALLOW_METHODS, b"GET"),
                    (MAX_AGE, b"600"),
                    (b"vary", b"Origin"),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", b"22"),
                ],
                403,
                b"Disallowed CORS origin",
            ),
            (
                b"http://e.com",
                ["http://e.net"],
                [
                    (ALLOW_METHODS, b"GET"),
                    (MAX_AGE, b"600"),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", b"22"),
                ],
                403,
                b"Disallowed CORS origin",
            ),
        ],
        ids=[
            "wildcard",
            "multiple",
            "single",
            "disallowed_multiple",
            "disallowed_single",
        ],
    )
    async def test_preflight_response(
        self, from_origin, options_origins, expected_headers, options_status, body
    ):
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": [
                    (REQUEST_METHOD, b"GET"),
                    (b"origin", from_origin),
                ],
            },
            expected_output={
                "status": options_status,
                "headers": expected_headers,
                "body": body,
            },
            cors_options={"origins": options_origins},
        )

    @pytest.mark.asyncio
    async def test_simple_response_with_regex_allowed_origins(self):
        cors_options = {
            "allow_origin_regex": r"http://e\..*",
            "allow_methods": ["PATCH"],
        }
        await do_cors_response(
            scope={
                "method": "GET",
                "headers": [
                    (b"origin", b"http://e.com"),
                    (REQUEST_METHOD, b"PATCH"),
                ],
            },
            expected_output={
                "status": 200,
                "headers": [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (b"vary", b"Origin"),
                    (b"content-length", b"17"),
                    (b"content-type", b"application/json"),
                ],
                "body": b'{"hello":"world"}',
            },
            cors_options=cors_options,
        )
        await do_cors_response(
            scope={
                "method": "GET",
                "headers": [
                    (b"origin", b"http://f.net"),
                    (REQUEST_METHOD, b"POST"),
                ],
            },
            expected_output={
                "status": 200,
                "headers": [
                    # no cors headers
                    (b"content-length", b"17"),
                    (b"content-type", b"application/json"),
                ],
                "body": b'{"hello":"world"}',
            },
            cors_options=cors_options,
        )

    @pytest.mark.asyncio
    async def test_preflight_response_with_regex_allowed_origins(self):
        cors_options = {
            "allow_origin_regex": r"http://e\..*",
            "allow_methods": ["PATCH"],
        }
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": [
                    (b"origin", b"http://e.com"),
                    (REQUEST_METHOD, b"PATCH"),
                ],
            },
            expected_output={
                "status": 204,
                "headers": [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (ALLOW_METHODS, b"PATCH"),
                    (MAX_AGE, b"600"),
                    (b"vary", b"Origin"),
                ],
                "body": b"",
            },
            cors_options=cors_options,
        )
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": [
                    (b"origin", b"http://f.org"),
                    (REQUEST_METHOD, b"PATCH"),
                ],
            },
            expected_output={
                "status": 403,
                "headers": [
                    (ALLOW_METHODS, b"PATCH"),
                    (MAX_AGE, b"600"),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", b"22"),
                    (b"vary", b"Origin"),
                ],
                "body": b"Disallowed CORS origin",
            },
            cors_options=cors_options,
        )

    async def test_simple_response_with_no_origin(self):
        await do_cors_response(
            scope={
                "method": "GET",
                "headers": [],
            },
            expected_output={
                "status": 200,
                "headers": [
                    # no cors headers
                    (b"content-length", b"17"),
                    (b"content-type", b"application/json"),
                ],
                "body": b'{"hello":"world"}',
            },
            cors_options={
                "origins": ["http://e.com"],
            },
        )

    async def test_preflight_response_with_no_origin(self):
        # if you don't provide the origin header, this isn't a valid cors preflight request.
        # we should get a regular options response
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": [(REQUEST_METHOD, b"GET")],
            },
            expected_output={
                "status": 200,
                "headers": [
                    (b"content-length", b"2"),
                    (b"allow", b"GET, OPTIONS"),
                ],
                "body": b"OK",
            },
            cors_options={"origins": ["*"], "allow_methods": ["GET"]},
        )


@pytest.mark.asyncio
class TestAllowMethods:
    @pytest.mark.parametrize(
        "allow_methods",
        [["*"], ["GET", "POST"], ["GET"]],
        ids=[
            "wildcard",
            "multiple",
            "single",
        ],
    )
    async def test_simple_response(self, allow_methods):
        await do_cors_response(
            scope={
                "method": "GET",
                "headers": [(b"origin", b"http://e.com")],
            },
            expected_output={
                "status": 200,
                "headers": [
                    # allow methods is not included in simple responses
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (b"content-length", b"17"),
                    (b"content-type", b"application/json"),
                ],
                "body": b'{"hello":"world"}',
            },
            cors_options={
                "origins": ["http://e.com"],
                "allow_methods": allow_methods,
            },
        )

    @pytest.mark.parametrize(
        "requested_headers, options_status, expected_headers, body, allow_methods",
        [
            (
                [],
                200,
                [(b"allow", b"GET, OPTIONS"), (b"content-length", b"2")],
                b"OK",
                ["*"],
            ),
            (
                [],
                200,
                [(b"allow", b"GET, OPTIONS"), (b"content-length", b"2")],
                b"OK",
                ["GET", "POST"],
            ),
            (
                [],
                200,
                [(b"allow", b"GET, OPTIONS"), (b"content-length", b"2")],
                b"OK",
                ["GET"],
            ),
            (
                [(REQUEST_METHOD, b"GET")],
                204,
                [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_METHODS, b"DELETE, GET, PATCH, POST, PUT"),
                ],
                b"",
                ["*"],
            ),
            (
                [(REQUEST_METHOD, b"GET")],
                204,
                [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_METHODS, b"GET, POST"),
                ],
                b"",
                ["GET", "POST"],
            ),
            (
                [(REQUEST_METHOD, b"GET")],
                204,
                [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_METHODS, b"GET"),
                ],
                b"",
                ["GET"],
            ),
            (
                [(REQUEST_METHOD, b"GET")],
                403,
                [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_METHODS, b"POST"),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", b"22"),
                ],
                b"Disallowed CORS method",
                ["POST"],
            ),
            (
                [(REQUEST_METHOD, b"GET")],
                403,
                [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_METHODS, b"POST, PUT"),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", b"22"),
                ],
                b"Disallowed CORS method",
                ["POST", "PUT"],
            ),
        ],
        ids=[
            "wildcard",
            "multiple",
            "single",
            "requested_wildcard",
            "requested_multiple",
            "requested_single",
            "disallowed_multiple",
            "disallowed_single",
        ],
    )
    async def test_preflight_response(
        self, requested_headers, options_status, expected_headers, body, allow_methods
    ):
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": requested_headers
                + [
                    (b"origin", b"http://e.com"),
                ],
            },
            expected_output={
                "status": options_status,
                "headers": expected_headers,
                "body": body,
            },
            cors_options={
                "origins": ["http://e.com"],
                "allow_methods": allow_methods,
            },
        )


@pytest.mark.asyncio
class TestAllowHeaders:
    @pytest.mark.parametrize(
        "allow_headers",
        [["*"], ["GET", "POST"], ["GET"]],
        ids=[
            "wildcard",
            "multiple",
            "single",
        ],
    )
    async def test_simple_response(self, allow_headers):
        await do_cors_response(
            scope={
                "method": "GET",
                "headers": [(b"origin", b"http://e.com")],
            },
            expected_output={
                "status": 200,
                "headers": [
                    # allow headers is not included in simple responses
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (b"content-length", b"17"),
                    (b"content-type", b"application/json"),
                ],
                "body": b'{"hello":"world"}',
            },
            cors_options={
                "origins": ["http://e.com"],
                "allow_headers": allow_headers,
            },
        )

    @pytest.mark.parametrize(
        "request_headers, options_status, expected_headers, body, allow_headers",
        [
            (
                [],
                204,
                [
                    (ALLOW_METHODS, b"GET"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                ],
                b"",
                ["*"],
            ),
            (
                [],
                204,
                [
                    (ALLOW_METHODS, b"GET"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_HEADERS, b"X-Header1, X-Header2"),
                ],
                b"",
                ["X-Header1", "X-Header2"],
            ),
            (
                [],
                204,
                [
                    (ALLOW_METHODS, b"GET"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_HEADERS, b"X-Header1"),
                ],
                b"",
                ["X-Header1"],
            ),
            (
                [(REQUEST_HEADERS, b"X-Header1")],
                204,
                [
                    (ALLOW_METHODS, b"GET"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_HEADERS, b"X-Header1"),
                ],
                b"",
                ["*"],
            ),
            (
                [(REQUEST_HEADERS, b"X-Header1")],
                204,
                [
                    (ALLOW_METHODS, b"GET"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_HEADERS, b"X-Header1, X-Header2"),
                ],
                b"",
                ["X-Header1", "X-Header2"],
            ),
            (
                [(REQUEST_HEADERS, b"X-Header1")],
                204,
                [
                    (ALLOW_METHODS, b"GET"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_HEADERS, b"X-Header1"),
                ],
                b"",
                ["X-Header1"],
            ),
            (
                [(REQUEST_HEADERS, b"X-Header3")],
                403,
                [
                    (ALLOW_METHODS, b"GET"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_HEADERS, b"X-Header1, X-Header2"),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", b"23"),
                ],
                b"Disallowed CORS headers",
                ["X-Header1", "X-Header2"],
            ),
            (
                [(REQUEST_HEADERS, b"X-Header3")],
                403,
                [
                    (ALLOW_METHODS, b"GET"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (MAX_AGE, b"600"),
                    (ALLOW_HEADERS, b"X-Header1"),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", b"23"),
                ],
                b"Disallowed CORS headers",
                ["X-Header1"],
            ),
        ],
        ids=[
            "wildcard",
            "multiple",
            "single",
            "requested_wildcard",
            "requested_multiple",
            "requested_single",
            "disallowed_multiple",
            "disallowed_single",
        ],
    )
    async def test_preflight_response(
        self, request_headers, options_status, expected_headers, body, allow_headers
    ):
        headers_by_status = [] if options_status == 204 else []
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": request_headers
                + [
                    (REQUEST_METHOD, b"GET"),
                    (b"origin", b"http://e.com"),
                ],
            },
            expected_output={
                "status": options_status,
                "headers": expected_headers + headers_by_status,
                "body": body,
            },
            cors_options={
                "origins": ["http://e.com"],
                "allow_headers": allow_headers,
            },
        )


@pytest.mark.asyncio
class TestExposeHeaders:
    async def test_simple_response(self):
        await do_cors_response(
            scope={
                "method": "GET",
                "headers": [
                    (b"origin", b"http://e.com"),
                    (REQUEST_METHOD, b"GET"),
                ],
            },
            expected_output={
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", b"17"),
                    (EXPOSE_HEADERS, b"X-Exposed, X-Exposed2"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                ],
                "body": b'{"hello":"world"}',
            },
            cors_options={
                "origins": ["http://e.com"],
                "expose_headers": ["X-Exposed", "X-Exposed2"],
            },
        )

    async def test_preflight_response(self):
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": [
                    (b"origin", b"http://e.com"),
                    (REQUEST_METHOD, b"GET"),
                ],
            },
            expected_output={
                "status": 204,
                "headers": [
                    # expose headers are simple response only
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (ALLOW_METHODS, b"GET"),
                    (MAX_AGE, b"600"),
                ],
                "body": b"",
            },
            cors_options={
                "origins": ["http://e.com"],
                "expose_headers": ["X-Exposed", "X-Exposed2"],
            },
        )


@pytest.mark.asyncio
class TestAllowCredentials:
    async def test_preflight_response_with_allow_credentials(self):
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": [
                    (b"origin", b"http://e.com"),
                    (REQUEST_METHOD, b"GET"),
                ],
            },
            expected_output={
                "status": 204,
                "headers": [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (ALLOW_METHODS, b"GET"),
                    (b"access-control-allow-credentials", b"true"),
                    (MAX_AGE, b"600"),
                ],
                "body": b"",
            },
            cors_options={
                "origins": ["http://e.com"],
                "allow_credentials": True,
            },
        )


@pytest.mark.asyncio
async def test_preflight_response_with_custom_max_age():
    await do_cors_response(
        scope={
            "method": "OPTIONS",
            "headers": [
                (b"origin", b"http://e.com"),
                (REQUEST_METHOD, b"GET"),
            ],
        },
        expected_output={
            "status": 204,
            "headers": [
                (ALLOW_ORIGIN, b"http://e.com"),
                (ALLOW_METHODS, b"GET"),
                (MAX_AGE, b"6000"),
            ],
            "body": b"",
        },
        cors_options={
            "origins": ["http://e.com"],
            "max_age": 6000,
        },
    )


@pytest.mark.asyncio
async def test_non_http_scope():
    cors_app = CorsASGIApp(app=app, origins=["*"])
    communicator = WebsocketCommunicator(application=cors_app, path="/")
    try:
        connected, _subprotocol = await communicator.connect()
        assert connected
        await communicator.send_json_to({"hello": "world"})
        response = await communicator.receive_json_from()
        assert response == {"hello": "world"}
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
class TestASGI2:
    async def test_asgi2_preflight_response(self):
        await do_cors_response(
            scope={
                "method": "OPTIONS",
                "headers": [
                    (b"origin", b"http://e.com"),
                    (REQUEST_METHOD, b"GET"),
                ],
            },
            expected_output={
                "status": 204,
                "headers": [
                    (ALLOW_ORIGIN, b"http://e.com"),
                    (ALLOW_METHODS, b"GET"),
                    (MAX_AGE, b"600"),
                ],
                "body": b"",
            },
            cors_app=CorsASGIApp(app=ASGI2app, origins=["http://e.com"]),
        )

    async def test_asgi2_simple_response(self):
        await do_cors_response(
            scope={
                "method": "GET",
                "headers": [
                    (b"origin", b"http://e.com"),
                    (REQUEST_METHOD, b"GET"),
                ],
            },
            expected_output={
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", b"17"),
                    (ALLOW_ORIGIN, b"http://e.com"),
                ],
                "body": b'{"hello":"world"}',
            },
            cors_app=CorsASGIApp(app=ASGI2app, origins=["http://e.com"]),
        )

    async def test_asgi2_non_http(self):
        cors_app = CorsASGIApp(app=ASGI2app, origins=["*"])
        communicator = WebsocketCommunicator(application=cors_app, path="/")
        try:
            connected, _subprotocol = await communicator.connect()
            assert connected
            await communicator.send_json_to({"hello": "world"})
            response = await communicator.receive_json_from()
            assert response == {"hello": "world"}
        finally:
            await communicator.disconnect()
