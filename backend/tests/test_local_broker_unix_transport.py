"""Owner-only Unix connector regression for the local broker transport.

Run with: python -m unittest backend/tests/test_local_broker_unix_transport.py
No external API or production model requests are issued.
"""
from __future__ import annotations

import asyncio
import ast
import importlib.util
import os
from pathlib import Path
import socket
import stat
import sys
import types
import unittest
import uuid
from unittest.mock import patch

import aiohttp

MODULE = (
    Path(__file__).resolve().parents[1]
    / "open_webui" / "utils" / "session_pool.py"
)


def load_transport_module():
    """Load the transport module without initialising the OpenWebUI server."""
    package = types.ModuleType("open_webui")
    package.__path__ = []
    utils = types.ModuleType("open_webui.utils")
    utils.__path__ = []
    env = types.ModuleType("open_webui.env")
    env.AIOHTTP_CLIENT_TIMEOUT = 30
    env.AIOHTTP_CLIENT_STREAM_IDLE_TIMEOUT = 30
    env.AIOHTTP_POOL_CONNECTIONS = 20
    env.AIOHTTP_POOL_CONNECTIONS_PER_HOST = 10
    env.AIOHTTP_POOL_DNS_TTL = 300
    misc = types.ModuleType("open_webui.utils.misc")

    async def stream_chunks_handler(content):
        async for data in content.iter_any():
            yield data

    misc.stream_chunks_handler = stream_chunks_handler
    replacements = {
        "open_webui": package,
        "open_webui.utils": utils,
        "open_webui.env": env,
        "open_webui.utils.misc": misc,
    }
    with patch.dict(sys.modules, replacements):
        spec = importlib.util.spec_from_file_location(
            "_local_broker_test_pool", MODULE
        )
        assert spec is not None and spec.loader is not None
        target = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(target)
        return target


class LocalBrokerTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pool = load_transport_module()
        self.path = Path.home() / (
            ".owui-uds-test-" + uuid.uuid4().hex[:10] + ".sock"
        )
        assert len(os.fsencode(self.path)) < 104
        self.assertFalse(self.path.exists())
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(self.path))
        self.listener.listen(2)
        os.chmod(self.path, 0o600)
        self.pool.BROKER_SOCKET = self.path

    async def asyncTearDown(self):
        await self.pool.close_session()
        self.listener.close()
        if self.path.exists() or self.path.is_symlink():
            self.path.unlink()

    async def test_only_exact_owned_broker_route_can_use_unix(self):
        valid = "http://127.0.0.1:18081/v1/chat/completions"
        self.assertEqual(self.pool.local_broker_unix_socket(valid), str(self.path))
        for url in (
            "https://127.0.0.1:18081/v1/models",
            "http://127.0.0.1:18084/v1/models",
            "http://127.0.0.1:18081.attacker.invalid/v1/models",
            "http://user@127.0.0.1:18081/v1/models",
            "http://external.invalid/v1/models",
            "http://127.0.0.1:18081/health",
            None,
        ):
            with self.subTest(url=url):
                self.assertIsNone(self.pool.local_broker_unix_socket(url))

    async def test_owned_socket_permission_and_type_are_enforced(self):
        url = "http://127.0.0.1:18081/v1/models"
        os.chmod(self.path, 0o666)
        self.assertIsNone(self.pool.local_broker_unix_socket(url))
        os.chmod(self.path, 0o600)
        self.assertEqual(self.pool.local_broker_unix_socket(url), str(self.path))
        self.pool.BROKER_SOCKET = self.path.parent / (
            self.path.name + ".missing"
        )
        self.assertIsNone(self.pool.local_broker_unix_socket(url))

    async def test_primary_chat_completion_selects_route_bound_session(self):
        source = MODULE.parents[1] / "routers" / "openai.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        fn = next(
            n for n in tree.body
            if isinstance(n, ast.AsyncFunctionDef)
            and n.name == "generate_chat_completion"
        )
        calls = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "get_session"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0].args), 1)
        self.assertIsInstance(calls[0].args[0], ast.Name)
        self.assertEqual(calls[0].args[0].id, "request_url")

    async def test_connection_pool_reuse_and_fallback(self):
        url = "http://127.0.0.1:18081/v1/models"
        local = await self.pool.get_session(url)
        self.assertIsInstance(local.connector, aiohttp.UnixConnector)
        self.assertIs(await self.pool.get_session(url), local)
        foreign = await self.pool.get_session(
            "http://127.0.0.1:18084/v1/models"
        )
        self.assertIsNot(foreign, local)
        self.assertNotIsInstance(foreign.connector, aiohttp.UnixConnector)
        await self.pool.close_session()
        self.assertTrue(local.closed)
        self.assertTrue(foreign.closed)


if __name__ == "__main__":
    unittest.main()
