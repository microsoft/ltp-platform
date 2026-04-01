import asyncio
import aiohttp
import time
import argparse
import json
import os

FAILED_COUNT = 0
TOTAL_COUNT = 0
LOCK = asyncio.Lock()


async def log_failure(file, record):
    global FAILED_COUNT, TOTAL_COUNT
    async with LOCK:
        FAILED_COUNT += 1
        TOTAL_COUNT += 1
        pct = round(FAILED_COUNT / TOTAL_COUNT * 100, 2)
        record["failure_pct"] = pct
        record["failed_count"] = FAILED_COUNT
        record["total_count"] = TOTAL_COUNT
        file.write(json.dumps(record) + "\n")
        file.flush()


async def worker(session, url, model, file):
    global TOTAL_COUNT

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hello"}],
    }

    try:
        async with session.post(url, json=payload) as resp:
            status = resp.status

            if status != 200:
                text = await resp.text()

                record = {
                    "ts": time.time(),
                    "model": model,
                    "status": status,
                    "body": text[:200],
                }

                await log_failure(file, record)  # increments FAILED_COUNT + TOTAL_COUNT
            else:
                await resp.text()
                async with LOCK:
                    TOTAL_COUNT += 1

    except Exception as e:
        record = {
            "ts": time.time(),
            "model": model,
            "status": "EXCEPTION",
            "error": str(e),
        }

        await log_failure(file, record)  # increments FAILED_COUNT + TOTAL_COUNT


async def run_for_model(model, args, file, headers):
    connector = aiohttp.TCPConnector(
        limit=args.concurrency,
        force_close=True
    )
    timeout = aiohttp.ClientTimeout(total=args.timeout)

    stats = {
        "model": model,
        "requests": 0,
        "start": time.time(),
    }

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers=headers,
    ) as session:

        tasks = []

        for _ in range(args.requests):
            tasks.append(worker(session, args.url, model, file))

            if len(tasks) >= args.concurrency:
                await asyncio.gather(*tasks)
                stats["requests"] += len(tasks)
                tasks = []

        if tasks:
            await asyncio.gather(*tasks)
            stats["requests"] += len(tasks)

    stats["duration"] = time.time() - stats["start"]
    return stats


async def main_async(args):
    global FAILED_COUNT

    # ====== API KEY ======
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    headers = {}

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    models = args.models

    # ====== 打开失败日志文件 ======
    with open(args.failed_log, "w") as f:

        # 👉 每个 model 独立并发执行
        results = await asyncio.gather(
            *[run_for_model(m, args, f, headers) for m in models]
        )

    # ====== 打印统计 ======
    print("\n=== PER MODEL STATS ===")
    total_requests = 0
    total_time = 0

    for r in results:
        rps = r["requests"] / r["duration"]
        print(f"Model: {r['model']}")
        print(f"  Requests: {r['requests']}")
        print(f"  Time: {r['duration']:.2f}s")
        print(f"  RPS: {rps:.2f}")
        print()

        total_requests += r["requests"]
        total_time = max(total_time, r["duration"])

    print("=== OVERALL ===")
    print(f"Total Requests: {total_requests}")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Effective RPS: {total_requests / total_time:.2f}")
    print(f"Failures: {FAILED_COUNT}")
    print(f"Failed log file: {args.failed_log}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        default="https://<base_url>/model-proxy/v1/chat/completions",
    )
    parser.add_argument("--requests", type=int, default=600)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=500)

    parser.add_argument(
        "--models",
        type=lambda s: s.split(","),
        default="gpt-3,gpt-4,gpt-5,gpt-6,gpt-7,gpt-8,gpt-9",
    )

    parser.add_argument(
        "--failed-log",
        type=str,
        default="failed_requests.jsonl",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key or use OPENAI_API_KEY env",
    )

    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()