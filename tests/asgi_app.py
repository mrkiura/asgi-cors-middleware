async def app(scope, receive, send):
    if scope["type"] == "websocket":
        await send({"type": "websocket.accept"})
        while True:
            message = await receive()
            if message["type"] == "websocket.disconnect":
                break
            elif message["type"] == "websocket.receive":
                # echo
                await send({
                    "type": "websocket.send",
                    "text": message["text"],
                })
        return
    elif scope['type'] == 'http':
        is_get = scope['method'] == 'GET'
        is_options = scope['method'] == 'OPTIONS'
        is_homepage = scope['path'] == '/'
        if is_get and is_homepage:
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    (b'content-length', b'17'),
                    (b'content-type', b'application/json'),
                ],
            })
            await send({
                'type': 'http.response.body',
                'body': b'{"hello":"world"}',
            })
            return
        elif is_options and is_homepage:
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    (b'allow', b'GET, OPTIONS'),
                    (b'content-length', b'2'),
                ],
            })
            await send({
                'type': 'http.response.body',
                'body': b'OK',
            })
            return
    await send({
        'type': 'http.response.start',
        'status': 500,
        'headers': [
            (b'content-type', b'text/plain'),
        ],
    })
    await send({
        'type': 'http.response.body',
        'body': b'Internal Server Error',
    })
