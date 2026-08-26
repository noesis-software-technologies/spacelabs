"""Handler ASGI 'lifespan' minimal : accuse réception startup/shutdown pour un
arrêt propre sur les serveurs qui le supportent (uvicorn…). La logique de boot
est portée par apps.runtime.startup (indépendant du serveur)."""


class LifespanApp:
    async def __call__(self, scope, receive, send):
        assert scope["type"] == "lifespan"
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
