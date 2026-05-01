"""Read-only web UI for finished runs.

Import :func:`harness.web.app.create_app` for the FastAPI factory.
"""

from harness.web.app import create_app

__all__ = ["create_app"]
