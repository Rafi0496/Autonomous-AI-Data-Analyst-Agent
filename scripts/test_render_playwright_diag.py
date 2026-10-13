import sys
import time
from playwright.sync_api import sync_playwright

FRONTEND_URL = "https://autonomous-ai-data-analyst-frontend.onrender.com"
BACKEND_URL = "https://autonomous-ai-data-analyst-backend.onrender.com"

print(f"Testing deployed Render frontend: {FRONTEND_URL}")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

    failed_requests = []
    page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} - {req.failure}"))
    page.on("response", lambda res: print(f"HTTP {res.status} {res.url}") if res.status >= 400 else None)

    print("Navigating to /upload...")
    res = page.goto(f"{FRONTEND_URL}/upload", timeout=60000, wait_until="networkidle")
    print(f"Page response: {res.status if res else 'None'}")
    time.sleep(3)

    print("Capturing initial screenshot...")
    page.screenshot(path="data/demo_outputs/screenshots/diag_upload_page.png")

    print("\n--- Console Logs ---")
    for log in console_logs[-15:]:
        print(log)

    print("\n--- Failed Requests ---")
    for req in failed_requests:
        print(req)

    # Check button text on page
    buttons = page.locator("button").all_text_contents()
    print("\nButtons found on page:", buttons[:10])

    # Try clicking "Load Benchmark" button if found
    load_btn = page.locator("button:has-text('Load Benchmark')").first
    if load_btn.is_visible():
        print("Clicking 'Load Benchmark'...")
        load_btn.click()
        time.sleep(5)
        page.screenshot(path="data/demo_outputs/screenshots/diag_after_benchmark_click.png")
        print("After click console logs:")
        for log in console_logs[-10:]:
            print(log)
    else:
        print("'Load Benchmark' button not visible")

    # Navigate to chat
    print("\nNavigating to /chat...")
    page.goto(f"{FRONTEND_URL}/chat", timeout=60000, wait_until="networkidle")
    time.sleep(3)
    page.screenshot(path="data/demo_outputs/screenshots/diag_chat_page.png")
    
    # Try typing 'Hi' in chat
    chat_input = page.locator("textarea, input[type='text']").first
    if chat_input.is_visible():
        print("Typing 'Hi' into chat input...")
        chat_input.fill("Hi")
        # Find send button
        send_btn = page.locator("button:has-text('Send'), button:has([data-icon='send']), button:has([data-icon='arrow-up'])").first
        if send_btn.is_visible():
            print("Clicking Send button...")
            send_btn.click()
            time.sleep(6)
            page.screenshot(path="data/demo_outputs/screenshots/diag_after_chat_send.png")
            print("Chat page messages / text:")
            body_text = page.locator("body").inner_text()
            print("\n".join([line for line in body_text.splitlines() if "Hi" in line or "Error" in line or "analyst" in line or "Guest" in line][:10]))

    browser.close()
    print("Done diagnosis script.")
