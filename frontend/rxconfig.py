import os
import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin

is_prod = os.getenv("ENVIRONMENT", "").lower() in ("prod", "production") or os.getenv("RENDER") is not None

config = rx.Config(
    app_name="frontend",
    telemetry_enabled=False,
    backend_port=int(os.getenv("PORT", "3000")) if is_prod else 8001,
    frontend_port=int(os.getenv("PORT", "3000")),
    plugins=[SitemapPlugin()],
)

