"""Start the environment HTTP server."""

import os

import uvicorn

from environment.api import app


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("HTTP_HOST", "127.0.0.1"),
        port=int(os.getenv("HTTP_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
