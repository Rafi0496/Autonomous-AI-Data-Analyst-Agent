import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="frontend",
    telemetry_enabled=False,
    backend_port=8001,
    frontend_port=3000,
    plugins=[SitemapPlugin()],
)
