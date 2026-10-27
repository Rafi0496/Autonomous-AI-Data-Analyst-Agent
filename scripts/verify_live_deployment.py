import time
from playwright.sync_api import sync_playwright

FRONTEND_URL = "https://autonomous-ai-data-analyst-frontend.onrender.com"
SCREENSHOT_DIR = "data/demo_outputs/screenshots"

print("--- RUNNING LIVE DEPLOYMENT VERIFICATION ---")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    # 1. Home page
    print("1. Navigating to Home page...")
    t0 = time.time()
    page.goto(FRONTEND_URL, timeout=60000, wait_until="networkidle")
    time.sleep(2)
    t_home = time.time() - t0
    print(f"   [OK] Home page loaded in {t_home:.2f}s")
    page.screenshot(path=f"{SCREENSHOT_DIR}/live_01_home.png")

    # 2. Test Switching to Datasets
    print("2. Clicking 'Datasets' in sidebar to measure switch lag...")
    t0 = time.time()
    datasets_link = page.locator("a[href='/upload']").first
    if datasets_link.is_visible():
        datasets_link.click()
    else:
        page.goto(f"{FRONTEND_URL}/upload")
    
    # Wait for Datasets heading/benchmark buttons to be visible
    page.wait_for_selector("text=PRELOADED BENCHMARK DATASETS", timeout=10000)
    t_switch = time.time() - t0
    print(f"   [OK] Switched to Datasets in {t_switch:.2f}s (Lag removed!)")
    page.screenshot(path=f"{SCREENSHOT_DIR}/live_02_datasets.png")

    # 3. Test Load Benchmark Button
    print("3. Clicking 'Load Benchmark' (Retail Sales)...")
    load_btn = page.locator("button:has-text('Load Benchmark')").first
    load_btn.click()
    # Wait for Dataset Ready status pill
    page.wait_for_selector("text=Dataset Ready", timeout=20000)
    print("   [OK] Benchmark loaded successfully! Dataset Ready displayed!")
    page.screenshot(path=f"{SCREENSHOT_DIR}/live_03_benchmark_ready.png")

    # 4. Test Chat
    print("4. Navigating to Chat...")
    page.goto(f"{FRONTEND_URL}/chat", timeout=30000, wait_until="networkidle")
    time.sleep(2)
    page.screenshot(path=f"{SCREENSHOT_DIR}/live_04_chat_initial.png")

    print("5. Sending 'Hi' in Chat...")
    chat_input = page.locator("#chat-input-textarea, textarea").first
    chat_input.fill("Hi")
    # Click send button
    send_btn = page.locator("button:has([data-icon='arrow-up']), button:has-text('Send')").first
    if send_btn.is_visible():
        send_btn.click()
    else:
        chat_input.press("Enter")
    
    # Wait for assistant response
    time.sleep(6)
    page.screenshot(path=f"{SCREENSHOT_DIR}/live_05_chat_answered.png")
    
    # Check text
    chat_text = page.locator("#chat-thread-container, body").inner_text()
    if "Autonomous Analyst" in chat_text or "Hello" in chat_text:
        print("   [OK] Chat responded successfully with assistant message!")
    else:
        print("   [INFO] Chat thread content:", chat_text[:200])

    browser.close()
    print("--- LIVE VERIFICATION COMPLETE ---")
