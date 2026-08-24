"""Production entrypoint — binds 0.0.0.0:$PORT so PaaS platforms can route.

Local dev keeps using `uvicorn app.main:app` directly; this wrapper exists for
deploy targets that assign the port at runtime and require an external bind.
"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
