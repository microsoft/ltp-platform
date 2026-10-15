import asyncio
import io
import json
import os
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from aiohttp import web


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "src" / "pylon" / "deploy" / "pylon-config"


class InferenceToolsTests(unittest.TestCase):
    def test_model_defaults_and_connection_mode(self):
        module = runpy.run_path(str(ROOT / "tools" / "test_inference.py"))
        captured = []

        async def capture_args(args):
            captured.append(args)

        with patch.dict(module["main"].__globals__, main_async=capture_args):
            with patch("sys.argv", ["test_inference.py"]):
                module["main"]()
            with patch("sys.argv", [
                "test_inference.py", "--models", "a,b", "--force-close",
            ]):
                module["main"]()

        self.assertEqual(captured[0].models, [
            "gpt-3", "gpt-4", "gpt-5", "gpt-6", "gpt-7", "gpt-8", "gpt-9",
        ])
        self.assertFalse(captured[0].force_close)
        self.assertEqual(captured[1].models, ["a", "b"])
        self.assertTrue(captured[1].force_close)


class AsyncInferenceToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_metadata_is_stable_per_completion(self):
        module = runpy.run_path(str(ROOT / "tools" / "mock_inference_server.py"))

        async def collect():
            events = [
                event async for event in
                module["stream_response"]("mock-gpt-4", "abcdefghijk")
            ]
            self.assertEqual(events[-1], "data: [DONE]\n\n")
            return [json.loads(event[6:]) for event in events[:-1]]

        first = await collect()
        second = await collect()
        self.assertEqual(len(first), 3)
        self.assertEqual(len({chunk["id"] for chunk in first}), 1)
        self.assertEqual(len({chunk["created"] for chunk in first}), 1)
        self.assertNotEqual(first[0]["id"], second[0]["id"])
        self.assertEqual("".join(
            chunk["choices"][0]["delta"]["content"] for chunk in first
        ), "abcdefghijk")

    async def test_connection_reuse_and_force_close(self):
        module = runpy.run_path(str(ROOT / "tools" / "test_inference.py"))
        transports = []

        async def handle(request):
            transports.append(request.transport)
            self.assertEqual((await request.json())["model"], "mock-gpt-4")
            return web.json_response({"ok": True})

        app = web.Application()
        app.router.add_post("/v1/chat/completions", handle)
        runner = web.AppRunner(app)
        await runner.setup()
        try:
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = runner.addresses[0][1]
            for force_close in (False, True):
                with self.subTest(force_close=force_close):
                    transports.clear()
                    args = SimpleNamespace(
                        url=f"http://127.0.0.1:{port}/v1/chat/completions",
                        requests=3, concurrency=1, timeout=5,
                        force_close=force_close,
                    )
                    failed_log = io.StringIO()
                    stats = await module["run_for_model"](
                        "mock-gpt-4", args, failed_log, {},
                    )
                    self.assertEqual(stats["requests"], 3)
                    self.assertEqual(failed_log.getvalue(), "")
                    self.assertEqual(len(set(transports)), 3 if force_close else 1)
        finally:
            await runner.cleanup()


class PylonRenderingTests(unittest.TestCase):
    def render(self, uri):
        outputs = {}

        def open_config(path, mode):
            if mode == "r":
                return io.StringIO(
                    (CONFIG_DIR / Path(path).name).read_text(encoding="utf-8")
                )
            outputs[path] = io.StringIO()
            return outputs[path]

        env = {} if uri is None else {"MODEL_PROXY_URI": uri}
        code = compile(
            (CONFIG_DIR / "render.py").read_text(encoding="utf-8"),
            str(CONFIG_DIR / "render.py"), "exec",
        )
        with patch.dict(os.environ, env, clear=True):
            exec(code, {"open": open_config})
        return {path: value.getvalue() for path, value in outputs.items()}

    def test_http_and_https_upstreams(self):
        for uri, address, scheme, path, host in [
            ("http://10.0.0.1:9999", "10.0.0.1:9999", "http", "", "10.0.0.1"),
            ("http://backend.example", "backend.example:80",
             "http", "", "backend.example"),
            ("https://backend.example", "backend.example:443",
             "https", "", "backend.example"),
            ("https://backend.example:8443/api/",
             "backend.example:8443", "https", "/api", "backend.example"),
            ("http://[::1]:9999", "[::1]:9999", "http", "", "::1"),
        ]:
            with self.subTest(uri=uri):
                outputs = self.render(uri)
                nginx = outputs["/root/nginx.conf"]
                location = outputs["/root/location.conf"]
                self.assertIn(f"server {address};", nginx)
                self.assertIn(
                    f"proxy_pass {scheme}://model_proxy_upstream{path}/$1$is_args$args;",
                    location,
                )
                self.assertEqual("proxy_ssl_server_name on;" in location, scheme == "https")
                if scheme == "https":
                    self.assertIn(f"proxy_ssl_name {host};", location)

    def test_optional_model_proxy(self):
        outputs = self.render(None)
        self.assertNotIn("model_proxy_upstream", outputs["/root/nginx.conf"])
        self.assertNotIn("model_proxy_upstream", outputs["/root/location.conf"])

    def test_invalid_backend_urls_fail(self):
        for uri in [
            "ftp://backend.example", "https:///missing-host",
            "http://backend.example:invalid", "http://backend.example:65536",
            "https://user:password@backend.example",
            "https://backend.example?query=value",
            "https://backend.example#fragment",
        ]:
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                self.render(uri)


if __name__ == "__main__":
    unittest.main()
