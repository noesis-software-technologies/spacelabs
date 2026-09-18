"""Proxy TCP : expose le relais extension OpenClaw (127.0.0.1:18799) sur l'IP WSL,
pour que Chrome (Windows) puisse le joindre sans toucher à .wslconfig."""
import asyncio
import sys

LISTEN_HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
LISTEN_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 18799
DEST_HOST = "127.0.0.1"
DEST_PORT = 18799


async def pipe(reader, writer):
    try:
        while not reader.at_eof():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(client_reader, client_writer):
    try:
        dst_reader, dst_writer = await asyncio.open_connection(DEST_HOST, DEST_PORT)
    except Exception:
        client_writer.close()
        return
    await asyncio.gather(
        pipe(client_reader, dst_writer),
        pipe(dst_reader, client_writer),
    )


async def main():
    server = await asyncio.start_server(handle, LISTEN_HOST, LISTEN_PORT)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"relay proxy listening on {addrs} -> {DEST_HOST}:{DEST_PORT}", flush=True)
    async with server:
        await server.serve_forever()


asyncio.run(main())
