#!/usr/bin/env python3
"""Thin TCP client for the AbletonMCP remote script (port 9877).

Speaks the same JSON protocol as the MCP server, without needing an MCP
session — usable from scripts and the render/critic loop.
"""
import json
import socket


class LiveMCP:
    def __init__(self, host="localhost", port=9877, timeout=15.0):
        self.addr = (host, port)
        self.timeout = timeout

    def cmd(self, command_type, **params):
        s = socket.socket()
        s.settimeout(self.timeout)
        s.connect(self.addr)
        try:
            s.sendall(json.dumps({"type": command_type, "params": params}).encode())
            chunks = []
            while True:
                data = s.recv(65536)
                if not data:
                    break
                chunks.append(data)
                try:
                    resp = json.loads(b"".join(chunks).decode())
                    break
                except ValueError:
                    continue  # partial JSON, keep reading
        finally:
            s.close()
        if resp.get("status") != "success":
            raise RuntimeError(f"{command_type}: {resp.get('message', resp)}")
        return resp.get("result", {})


if __name__ == "__main__":
    import sys
    live = LiveMCP()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "get_session_info"
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(live.cmd(cmd, **params), indent=2))
