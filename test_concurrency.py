import asyncio
import time

import httpx


URL = "http://127.0.0.1:8000/chat"
REQUEST_COUNT = 10


async def send_request(
    client: httpx.AsyncClient,
    request_number: int,
) -> tuple[int, int, float]:
    payload = {
        "query": "beaches in Vizag",
        "original_query": "beaches in Vizag",
        "language": "English",
        "session_id": (
            f"async-concurrent-test-{request_number}-123456789"
        ),
    }

    started = time.perf_counter()

    try:
        response = await client.post(URL, json=payload)
        elapsed = time.perf_counter() - started
        return request_number, response.status_code, elapsed

    except httpx.HTTPError as exc:
        elapsed = time.perf_counter() - started
        print(
            f"Request {request_number} failed after "
            f"{elapsed:.2f}s: {type(exc).__name__}: {exc}"
        )
        return request_number, 0, elapsed


async def main() -> None:
    timeout = httpx.Timeout(
        connect=5.0,
        read=60.0,
        write=10.0,
        pool=5.0,
    )

    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=10,
    )

    started = time.perf_counter()

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
    ) as client:
        tasks = [
            send_request(client, number)
            for number in range(1, REQUEST_COUNT + 1)
        ]

        results = await asyncio.gather(*tasks)

    total_time = time.perf_counter() - started

    print()
    for number, status_code, elapsed in sorted(results):
        print(
            f"Request {number}: "
            f"status={status_code}, time={elapsed:.2f}s"
        )

    successful = sum(
        1 for _, status_code, _ in results
        if status_code == 200
    )

    print()
    print(f"Successful requests: {successful}/{REQUEST_COUNT}")
    print(f"Total concurrent test time: {total_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())