"""AgentAudit remote MCP server — streamable-HTTP mount (TECHSPEC §13 companion).

``mcp-server/server.mjs`` stays the LOCAL stdio path (Claude Desktop/Code,
Cursor spawn the process). This module exposes the SAME three tools over HTTP
so hosted clients — ChatGPT connectors/developer mode and claude.ai custom
integrations — can attach to the deployed API by URL alone:

    POST /mcp   JSON-RPC 2.0 over the streamable-HTTP transport

Transport settings (deliberate):
    stateless_http=True  — no Mcp-Session-Id bookkeeping; every POST is
                           self-contained → survives container swaps and needs
                           no sticky routing on the platform edge.
    json_response=True   — plain JSON replies, never an SSE stream → no
                           proxy buffering surprises, trivially verifiable
                           with curl.

Tools reuse the REST router handlers directly (same session layer as the
frontend), so MCP answers are exactly the payloads /api returns — including
the SCHEMA §7 error envelope when something is not found or refused.
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

SERVER_VERSION = "1.0.0"

mcp = FastMCP(
    "agentaudit-mcp",
    stateless_http=True,
    json_response=True,
)


async def _run(handler, *args):  # noqa: ANN002, ANN003 — heterogeneous router handlers
    """Shared tool body: run a REST router handler on its own DB session.

    AppError becomes the same structured envelope REST returns (E-codes stay
    machine-readable for the calling agent) instead of an opaque tool error.
    """
    from app.db.session import get_sessionmaker
    from app.errors import AppError, error_payload

    maker = get_sessionmaker()
    async with maker() as session:
        try:
            return await handler(*args, session)
        except AppError as exc:
            return error_payload(exc.code, exc.message, exc.details)


@mcp.tool()
async def audit_status(run_id: str) -> dict:
    """Get AgentAudit run status: trials done/total, cost, state."""
    from app.routers.audit import get_audit

    return await _run(get_audit, run_id)


@mcp.tool()
async def get_report(run_id: str) -> dict:
    """Full audit report: AgentReady score with CI, HHI, position bias, framing,
    coverage F_task with CI, invisible SKUs, revenue preview."""
    from app.routers.report import get_report

    return await _run(get_report, run_id)


@mcp.tool()
async def create_payment_link(run_id: str, sku: str) -> dict:
    """Create a Razorpay TEST-MODE payment link for a product from an audited
    catalog (idempotent per run+sku)."""
    from app.routers.payments import LinkRequest, create_link

    return await _run(create_link, LinkRequest(run_id=run_id, sku=sku))


def build_mcp_asgi_app():
    """ASGI callable for ``app.mount("/mcp", ...)"`` in main.py.

    A bare function (not ``FastMCP.streamable_http_app()``) on purpose: that
    helper returns a Starlette sub-app whose lifespan can never run under a
    parent mount, and its session-manager singleton refuses a second
    ``.run()``, which breaks every restart/reload/test cycle. We instead build
    one fresh manager per lifespan entry (:func:`mcp_lifespan`) and route
    through it here.
    """
    return _streamable_http_endpoint


async def _streamable_http_endpoint(scope, receive, send) -> None:  # noqa: ANN001
    """Raw ASGI endpoint — delegates to the active session manager."""
    manager = _Transport.manager
    assert manager is not None, "mcp_lifespan must run before serving /mcp"
    await manager.handle_request(scope, receive, send)


class _Transport:
    """Process-wide holder for the CURRENT session manager.

    Swapped on every lifespan entry: the SDK's StreamableHTTPSessionManager
    allows ``.run()`` exactly once per instance, while our app lifespan runs
    once per process boot AND once per TestClient context in tests.
    """

    manager: object | None = None


_Transport = _Transport()


@asynccontextmanager
async def mcp_lifespan(_: object | None = None) -> AsyncIterator[None]:
    """Run the MCP transport's task group inside the parent app lifespan."""
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    _Transport.manager = StreamableHTTPSessionManager(
        # No public accessor on FastMCP for the low-level server in 1.29.1;
        # we pin the exact SDK version, so this attribute is stable for us.
        app=mcp._mcp_server,  # noqa: SLF001
        event_store=None,     # stateless: nothing to replay across requests
        json_response=True,   # plain JSON replies — no SSE streams to buffer
        stateless=True,       # no Mcp-Session-Id bookkeeping / sticky routing
    )
    async with _Transport.manager.run():
        yield
