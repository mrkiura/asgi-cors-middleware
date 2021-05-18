# asgi-cors-middleware

Python package that allows whitelisting of urls on ASGI applications making it possible to perform cross origin requests from the browser.

## CORS in a nutshell

**Cross-Origin Resource Sharing (CORS)** allows a server to define any
 origins other than its own that are safe for the browser to load resources from.

Mozilla does a good job of explaining CORS [here](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS).

## Background

Assuming you have a web application that follows a client-server architecture, it's possible the frontend would be running on a server
different from the API. If the frontend application made a request to the API, this kind of request would be blocked by the browser.

For security reasons, browsers block cross origin requests by default.

A cross origin request is a request made to a server with a different url/ origin. To mitigate around this, we could simply add the url of the frontend application as an allowed origin on the API server.
Most web frameworks provide a way to do this or have third party libraries that achieve the same.

**asgi-cors-middleware** aims to provide a simple way to achieve the above for ASGI applications.

## Features

* Simple
* Works with most ASGI frameworks (Django, Starlette, FastAPI, channels)
* Works with Ariadne

## Installation

Can be installed via pip

```bash
pip install asgi-cors-middleware
```

## Usage

To use the middleware, just import it like so:

```python
from asgi_cors_middleware import CorsASGIApp
```

To start whitelisting origins, just wrap your asgi application instance with
`CorsASGIApp`.

```python

app = CorsASGIApp(
    app=asgi_app_instance,
    origins=["www.example.com"]
)
```

## Example

A simple HelloWorld application that whitelists the origins below:
* www.example.com
* localhost:9000

### Install an ASGI server

```bash
pip install uvicorn
```

Create a file called example.py and update it with the code below:

```python
from asgi_cors_middleware import CorsASGIApp

class HelloWorld:
    def __init__(self, scope):
        pass

    async def __call__(self, receive, send):
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
            ]
        })
        await send({
            'type': 'http.response.body',
            'body': b'Hello, world!',
        })

app = CorsASGIApp(
    app=HelloWorld,
    origins=[
        "www.example.com",
        "localhost:9000"
    ]
)
```

That's it. For real, that's really it. Now your application is all set to allow requests from www.example.com and localhost:9000.

### Run the app

```bash
uvicorn example:app
```

## Contributing

For guidance and instructions, please see [CONTRIBUTING.md](CONTRIBUTING.md)
