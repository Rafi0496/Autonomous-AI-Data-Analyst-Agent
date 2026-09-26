import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="frontend",
    telemetry_enabled=False,
    plugins=[SitemapPlugin()],
    tailwind={
        "theme": {
            "extend": {
                "colors": {
                    "brand": {
                        "500": "#6366f1",
                        "600": "#4f46e5",
                        "700": "#4338ca",
                    }
                }
            }
        },
    }
)
