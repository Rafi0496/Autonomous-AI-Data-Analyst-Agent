"""Main Reflex frontend application setup and route registration."""
import reflex as rx
from frontend.pages.chat import chat_page
from frontend.pages.dashboard import dashboard_page
from frontend.pages.reports import reports_page
from frontend.pages.settings import settings_page
from frontend.pages.upload import upload_page
from frontend.state import AppState

app = rx.App(
    theme=rx.theme(
        appearance="dark",
        has_background=True,
        accent_color="indigo",
        gray_color="slate",
        radius="medium"
    ),
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ]
)

# Register routes
app.add_page(upload_page, route="/", title="AutoAnalyst | Upload & Profiling", on_load=AppState.fetch_datasets)
app.add_page(upload_page, route="/upload", title="AutoAnalyst | Upload & Profiling", on_load=AppState.fetch_datasets)
app.add_page(dashboard_page, route="/dashboard", title="AutoAnalyst | Dashboard", on_load=AppState.on_load_dashboard)
app.add_page(chat_page, route="/chat", title="AutoAnalyst | Chat", on_load=AppState.on_load_dashboard)
app.add_page(reports_page, route="/reports", title="AutoAnalyst | Reports", on_load=AppState.on_load_reports)
app.add_page(settings_page, route="/settings", title="AutoAnalyst | Settings")
