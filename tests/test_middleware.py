import pytest
from asgiref.testing import ApplicationCommunicator as HttpCommunicator
from asgi_cors_middleware import CorsASGIApp
from .asgi_app import app


@pytest.mark.asyncio
async def test_init_app():
    communicator = HttpCommunicator(
        scope={"type": "http", "http_version": "1.0", "method": "GET", "path": "/"},
        application=app
    )
    await communicator.send_input({"type": "http.request"})
    output = await communicator.receive_output(1)
    assert output == {
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            (b'content-length', b'17'),
            (b'content-type', b'application/json')
        ]}
    output = await communicator.receive_output(1)
    assert output == {
        'type': 'http.response.body',
        'body': b'{"hello":"world"}'
    }


@pytest.mark.asyncio
async def test_whitelist_origin():
    cors_app = CorsASGIApp(
        app=app,
        origins=["www.example.com"]
    )
    scope = {
        "type": "http",
        "path": "/",
        "method": "OPTIONS",
        "headers": [
            (b"origin", b"http://www.example.com"),
            (b"access-control-request-method", b"post")
        ]
    }
    communicator = HttpCommunicator(application=cors_app, scope=scope)
    await communicator.send_input(
        {
            "type": "http",
            "method": "options",
            "headers": [
                [b"content-type", b"text/plain"],
                [b"access-control-request-method", b"post"],
                [b"origin", b"example.com"]
            ]
        }
    )
    output = await communicator.receive_output(timeout=1)
    assert (b'access-control-allow-origin', b'http://www.example.com') in \
           output["headers"]


@pytest.mark.asyncio
async def test_allow_all():
    cors_app = CorsASGIApp(
        app=app,
        origins=["*"]
    )
    scope = {
        "type": "http",
        "path": "/",
        "method": "OPTIONS",
        "headers": [
            (b"origin", b"http://www.example.com"),
            (b"access-control-request-method", b"post")
        ]
    }

    communicator = HttpCommunicator(
        application=cors_app,
        scope=scope
    )
    await communicator.send_input(
        {
            "type": "http",
            "method": "options",
            "headers": [
                [b"content-type", b"text/plain"],
                [b"access-control-request-method", b"post"],
                [b"origin", b"example.com"]
            ]
        }
    )
    output = await communicator.receive_output(timeout=1)
    assert (b'access-control-allow-origin', b'*') in output["headers"]


@pytest.fixture
def decorated_app():
    return CorsASGIApp(app=app, origins=["localhost"])
