"""Built-in lightweight HTTP asset server for hosting branding logos and banners."""

import logging
from pathlib import Path
from typing import Optional
from aiohttp import web

logger = logging.getLogger("secretsanta.asset_server")


class AssetServer:
    """Lightweight aiohttp web server to serve static assets for Discord embeds."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        assets_dir: Optional[Path] = None,
        event_name: str = "Secret Santa",
        public_url: str = "http://localhost:8080",
    ):
        self.host = host
        self.port = port
        self.assets_dir = Path(assets_dir) if assets_dir else Path("assets")
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.event_name = event_name
        self.public_url = public_url.rstrip("/")

        self.app = web.Application()
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._setup_routes()

    def _setup_routes(self):
        """Configure routes for asset serving and health checks."""
        # Static asset serving at /assets
        self.app.router.add_static(
            "/assets",
            path=str(self.assets_dir),
            show_index=False,
            follow_symlinks=True,
        )

        # Health & status endpoints
        self.app.router.add_get("/", self._handle_index)
        self.app.router.add_get("/health", self._handle_health)

    async def _handle_index(self, request: web.Request) -> web.Response:
        """Root status response."""
        data = {
            "app": "Secret Santa Asset Server",
            "event_name": self.event_name,
            "status": "online",
            "public_url": self.public_url,
            "assets_endpoint": f"{self.public_url}/assets",
        }
        return web.json_response(data)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint for reverse proxies (nginx, caddy, etc.)."""
        return web.json_response({"status": "ok", "event_name": self.event_name})

    async def start(self):
        """Start the HTTP server on the active event loop."""
        if self._runner is not None:
            return

        logger.info(
            "Starting asset HTTP server on %s:%d (Serving: %s | Public URL: %s)",
            self.host,
            self.port,
            self.assets_dir.resolve(),
            self.public_url,
        )
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self.host, port=self.port)
        await self._site.start()
        logger.info("Asset HTTP server running at http://%s:%d", self.host, self.port)

    async def stop(self):
        """Gracefully stop the HTTP server and release port."""
        if self._runner is not None:
            logger.info("Stopping asset HTTP server...")
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            logger.info("Asset HTTP server stopped.")
