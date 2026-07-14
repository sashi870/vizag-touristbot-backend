import asyncio
import time

from app.services.recommendation_service import ask_ollama


async def main() -> None:
    for attempt in range(1, 6):
        started = time.perf_counter()

        try:
            result = await ask_ollama(
                "Explain the difference between humidity and temperature"
            )
        except Exception as exc:
            result = f"Unexpected exception: {type(exc).__name__}: {exc}"

        elapsed = time.perf_counter() - started

        print()
        print(f"Attempt {attempt}")
        print(f"Time: {elapsed:.2f} seconds")
        print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())