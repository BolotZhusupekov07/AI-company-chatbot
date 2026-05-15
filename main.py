import asyncio
import logging
import sys

from configs import main_config

logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)


async def main() -> None:
    """Run the configured service entrypoint."""

    if main_config.MODE == "HTTP":
        from entrypoints.http import app_factory as http_app_factory

        await http_app_factory.create_app()


if __name__ == "__main__":
    asyncio.run(main())
