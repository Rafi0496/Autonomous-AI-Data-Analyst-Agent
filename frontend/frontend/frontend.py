"""Main Reflex frontend application setup and route registration."""
import reflex as rx
from frontend.pages.chat import chat_page
from frontend.pages.dashboard import dashboard_page
from frontend.pages.home import home_page
from frontend.pages.login import login_page
from frontend.pages.reports import reports_page
from frontend.pages.run import run_page
from frontend.pages.settings import settings_page
from frontend.pages.upload import upload_page
from frontend.state import AppState

# Remove the "Built with Reflex" sticky badge completely
rx.App._setup_sticky_badge = lambda self: None

app = rx.App(
    theme=rx.theme(
        appearance="dark",
        has_background=False,
    ),
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap",
        "/styles.css?v=4",
    ],
    head_components=[
        rx.el.link(rel="icon", href="/favicon.svg", type="image/svg+xml"),
    ],
)

# Register routes with zero-lag instant handlers
app.add_page(home_page, route="/", title="AutoAnalyst | Autonomous AI Data Analyst", on_load=AppState.on_load_home)
app.add_page(login_page, route="/login", title="AutoAnalyst | Sign In", on_load=AppState.on_load_login)
app.add_page(upload_page, route="/upload", title="AutoAnalyst | Datasets & Quality", on_load=AppState.on_load_upload)
app.add_page(run_page, route="/run", title="AutoAnalyst | Run Monitor", on_load=AppState.on_load_run)
app.add_page(dashboard_page, route="/dashboard", title="AutoAnalyst | Dashboard", on_load=AppState.on_load_dashboard)
app.add_page(chat_page, route="/chat", title="AutoAnalyst | Chat", on_load=AppState.on_load_chat)
app.add_page(reports_page, route="/reports", title="AutoAnalyst | Reports", on_load=AppState.on_load_reports)
app.add_page(settings_page, route="/settings", title="AutoAnalyst | Settings", on_load=AppState.on_load_settings)
