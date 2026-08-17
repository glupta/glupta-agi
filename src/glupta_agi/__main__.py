"""Local process entry point."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "glupta_agi.api:load_app",
        factory=True,
        host="127.0.0.1",
        port=8080,
        access_log=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
