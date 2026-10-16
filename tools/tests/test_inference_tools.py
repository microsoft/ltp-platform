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
    def test_mock_usage_totals(self):
        module = runpy.run_path(str(ROOT / "tools" / "mock_inference_server.py"))
        for content in ("", "hello", "longer mock response"):
            with self.subTest(content=content):
                with patch.object(module["random"], "randint", return_value=7) as randint:
                    usage = module["build_chat_response"]("mock-gpt-4", content)["usage"]
                randint.assert_called_once_with(5, 20)
                self.assertEqual(usage["prompt_tokens"], 7)
                self.assertEqual(usage["completion_tokens"], len(content))
                self.assertEqual(
                    usage["total_tokens"],
                    usage["prompt_tokens"] + usage["completion_tokens"],
                )

    def test_invalid_load_arguments(self):
        module = runpy.run_path(str(ROOT / "tools" / "test_inference.py"))
        for args in [
            ["--concurrency", "0"], ["--concurrency", "-1"],
            ["--requests", "-1"],
        ]:
            with self.subTest(args=args):
                with patch("sys.argv", ["test_inference.py"] + args):
                    with patch("sys.stderr", new_callable=io.StringIO):
                        with self.assertRaises(SystemExit) as error:
                            module["main"]()
                self.assertEqual(error.exception.code, 2)

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
    async def test_worker_pool_refills_before_slow_request_finishes(self):
        module = runpy.run_path(str(ROOT / "tools" / "test_inference.py"))
        slow_started = asyncio.Event()
        refilled = asyncio.Event()
        release_slow = asyncio.Event()
        started = 0
        active = 0
        peak_active = 0

        async def controlled_worker(session, url, model, file):
            nonlocal started, active, peak_active
            started += 1
            request_id = started
            active += 1
            peak_active = max(peak_active, active)
            try:
                if request_id == 1:
                    slow_started.set()
                    await release_slow.wait()
                else:
                    await slow_started.wait()
                    if request_id == 3:
                        refilled.set()
            finally:
                active -= 1

        args = SimpleNamespace(
            url="http://127.0.0.1", requests=7, concurrency=2,
            timeout=5, force_close=False,
        )
        with patch.dict(module["run_for_model"].__globals__, worker=controlled_worker):
            task = asyncio.create_task(module["run_for_model"](
                "mock-gpt-4", args, io.StringIO(), {},
            ))
            try:
                await asyncio.wait_for(refilled.wait(), timeout=2)
                self.assertFalse(release_slow.is_set())
            finally:
                release_slow.set()
                stats = await asyncio.wait_for(task, timeout=2)
        self.assertEqual(stats["requests"], 7)
        self.assertEqual(started, 7)
        self.assertEqual(peak_active, 2)
        self.assertEqual(active, 0)

    async def test_worker_pool_request_counts(self):
        module = runpy.run_path(str(ROOT / "tools" / "test_inference.py"))
        for requests, concurrency in [(0, 2), (1, 5), (7, 3)]:
            with self.subTest(requests=requests, concurrency=concurrency):
                completed = []

                async def record_worker(session, url, model, file):
                    completed.append(model)
                    await asyncio.sleep(0)

                args = SimpleNamespace(
                    url="http://127.0.0.1", requests=requests,
                    concurrency=concurrency, timeout=5, force_close=False,
                )
                with patch.dict(module["run_for_model"].__globals__, worker=record_worker):
                    stats = await module["run_for_model"](
                        "mock-gpt-4", args, io.StringIO(), {},
                    )
                self.assertEqual(stats["requests"], requests)
                self.assertEqual(len(completed), requests)

    async def test_stream_metadata_is_stable_per_completion(self):
        module = runpy.run_path(str(ROOT / "tools" / "mock_inference_server.py"))

        async def collect(content):
            events = [
                event async for event in
                module["stream_response"]("mock-gpt-4", content)
            ]
            self.assertEqual(events[-1], "data: [DONE]\n\n")
            chunks = [json.loads(event[6:]) for event in events[:-1]]
            self.assertEqual(chunks[-1]["choices"], [
                {"delta": {}, "index": 0, "finish_reason": "stop"},
            ])
            self.assertTrue(all(
                chunk["choices"][0]["finish_reason"] is None for chunk in chunks[:-1]
            ))
            self.assertEqual(len({chunk["id"] for chunk in chunks}), 1)
            self.assertEqual(len({chunk["created"] for chunk in chunks}), 1)
            self.assertTrue(all(
                chunk["object"] == "chat.completion.chunk"
                and chunk["model"] == "mock-gpt-4" for chunk in chunks
            ))
            self.assertEqual("".join(
                chunk["choices"][0]["delta"].get("content", "") for chunk in chunks
            ), content)
            return chunks

        first = await collect("abcdefghijk")
        second = await collect("abcdefghijk")
        empty = await collect("")
        self.assertEqual(len(first), 4)
        self.assertEqual(len(empty), 1)
        self.assertNotEqual(first[0]["id"], second[0]["id"])

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
                self.assertIn("zone model_proxy_upstream 64k;", nginx)
                self.assertIn(f"server {address} resolve;", nginx)
                self.assertIn("resolver 127.0.0.1;", nginx)
                self.assertIn(
                    f"proxy_pass {scheme}://model_proxy_upstream{path}/$1$is_args$args;",
                    location,
                )
                self.assertIn(f"proxy_set_header Host {address};", location)
                self.assertEqual("proxy_ssl_server_name on;" in location, scheme == "https")
                if scheme == "https":
                    self.assertIn(f"proxy_ssl_name {host};", location)

    def test_optional_model_proxy(self):
        outputs = self.render(None)
        self.assertNotIn("model_proxy_upstream", outputs["/root/nginx.conf"])
        self.assertNotIn("model_proxy_upstream", outputs["/root/location.conf"])

    def test_job_server_keeps_existing_behavior(self):
        location = self.render(None)["/root/location.conf"]
        job_server = location.split(
            r"location ~ ^/job-server/([^/]+):(\d+)/(.*)$ {", 1,
        )[1].split("\n}", 1)[0]
        self.assertIn("proxy_pass http://$1:$2/$3$is_args$args;", job_server)
        self.assertNotIn("proxy_next_upstream", job_server)
        for directive in ("proxy_connect_timeout", "proxy_read_timeout", "proxy_send_timeout"):
            self.assertIn(f"{directive} 180m;", job_server)
        self.assertIn("proxy_buffering off;", job_server)
        self.assertIn("proxy_cache off;", job_server)

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
