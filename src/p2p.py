"""Prototype P2P node: simple asyncio TCP peer with JSON messages and HMAC auth.

This is a minimal prototype for node-to-node communication suitable for early
experiments; production would use libp2p or an equivalent robust stack.
"""
import asyncio
import json
from typing import Callable
from .crypto_asym import sign_bytes, verify_bytes


class P2PNode:
    def __init__(self, host='127.0.0.1', port=9000, on_message: Callable[[dict], None]=None):
        self.host = host
        self.port = port
        self.server = None
        self.on_message = on_message

    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, self.port)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            data = await reader.readline()
            raw = data.rstrip(b"\n")
            meta_line = await reader.readline()
            meta = json.loads(meta_line.decode('utf-8'))
            sig = meta.get('sig')
            if not verify_bytes(raw, sig):
                writer.write(b'ERROR: signature invalid\n')
                await writer.drain()
                writer.close()
                return
            msg = json.loads(raw.decode('utf-8'))
            if self.on_message:
                self.on_message(msg)
            writer.write(b'OK\n')
            await writer.drain()
            writer.close()
        except Exception:
            try:
                writer.write(b'ERROR\n')
                await writer.drain()
                writer.close()
            except Exception:
                pass

    async def send(self, host, port, message: dict, timeout=5):
        reader, writer = await asyncio.open_connection(host, port)
        raw = json.dumps(message).encode('utf-8')
        sig = sign_bytes(raw)
        writer.write(raw + b"\n")
        writer.write(json.dumps({'sig': sig}).encode('utf-8') + b"\n")
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        writer.close()
        return line.decode('utf-8').strip()
