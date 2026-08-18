"""Local process entry point."""

from __future__ import annotations

import os

import uvicorn
from dbos import DBOS, DBOSConfig

from .settings import Settings


def main() -> None:
    settings = Settings.from_environment()
    config: DBOSConfig = {
        "name": "glupta-agi-crawl",
        "application_version": "0.2.5",
        "system_database_url": settings.dbos_system_database_url(),
    }
    DBOS(config=config)

    from .effects import initialize

    initialize(config["system_database_url"])

    # Import after DBOS is configured so workflow decorators register against
    # the initialized local runtime.
    from .api import app

    DBOS.launch()
    uvicorn.run(
        app,
        host=os.environ.get("GLUPTA_HOST", "127.0.0.1"),
        port=int(os.environ.get("GLUPTA_PORT", "8080")),
        access_log=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
