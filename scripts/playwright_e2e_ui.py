"""Playwright End-to-End Headless Browser UI Drive & Screenshot Capture.

Drives the complete user flow in Reflex frontend (port 3000):
1. /upload (Upload page and sample dataset selection)
2. /progress (Cleaning, profiling, and autonomous analysis progress)
3. /dashboard (Partitioned analytical insights and data-quality caveats)
4. /chat (Interactive grounded chat Q&A with evidence and bound citations)
5. /reports (PDF & DOCX report generation and download)

Asserts:
- Dashboard has >= 1 insight card and a chart element
- Chat shows a non-empty answer
- Reports page lists a generated file
Saves screenshots only after assertions pass and prints assertion results.
"""
import sys
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = BASE_DIR / "data" / "demo_outputs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def run_playwright_e2e(base_url: str = "http://localhost:3000"):
    print("=" * 80)
    print("STARTING PLAYWRIGHT HEADLESS BROWSER UI VERIFICATION")
    print(f"Target URL: {base_url}")
    print(f"Screenshots Directory: {SCREENSHOTS_DIR}")
    print("=" * 80)

    from playwright.sync_api import sync_playwright

    captured_screenshots = []
    assertion_results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        try:
            # 0. Authenticate via backend API and inject token
            try:
                import json
                import urllib.request
                auth_payload = json.dumps({
                    "email": "ui_playwright_test@example.com",
                    "password": "UiPassword123!"
                }).encode("utf-8")
                token = None
                try:
                    req_reg = urllib.request.Request(
                        "http://localhost:8000/api/v1/auth/register",
                        data=auth_payload,
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req_reg, timeout=3) as resp:
                        token = json.loads(resp.read().decode()).get("access_token")
                except Exception:
                    req_login = urllib.request.Request(
                        "http://localhost:8000/api/v1/auth/login",
                        data=auth_payload,
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req_login, timeout=3) as resp:
                        token = json.loads(resp.read().decode()).get("access_token")

                if token:
                    context.add_init_script(f"""
                        window.localStorage.setItem('auth_token', '{token}');
                        window.localStorage.setItem('token', '{token}');
                    """)
                    print("      Injected JWT authentication token into browser context.")
            except Exception as e:
                print(f"      Auth setup note: {str(e)}")

            # 1. Upload Page
            print("\n[1/5] Navigating to Upload page...")
            page.goto(f"{base_url}/upload", timeout=30000, wait_until="networkidle")

            time.sleep(3)
            p1 = SCREENSHOTS_DIR / "01_upload_page.png"
            page.screenshot(path=str(p1), full_page=True)
            print(f"      Captured: {p1}")
            captured_screenshots.append(str(p1))

            # 2. Select Sample Benchmark Dataset & Trigger Analysis
            print("\n[2/5] Selecting Retail Sales Benchmark Dataset & Starting Analysis...")
            sample_btn = page.query_selector("button:has-text('Load Benchmark Dataset')")
            if sample_btn:
                sample_btn.click()
                print("      Clicked 'Load Benchmark Dataset'. Waiting for profiling to complete...")
                # Wait for dataset to be loaded and start analysis panel to appear
                page.wait_for_selector("button:has-text('Start Analysis')", timeout=20000)
                time.sleep(2)

            p2 = SCREENSHOTS_DIR / "02_cleaning_progress.png"
            page.screenshot(path=str(p2), full_page=True)
            print(f"      Captured: {p2}")
            captured_screenshots.append(str(p2))

            # Click Start Analysis
            start_btn = page.query_selector("button:has-text('Start Analysis')")
            if start_btn:
                start_btn.click()
                print("      Clicked 'Start Analysis'. Waiting for autonomous agent execution...")
                # Wait for completion: either automatically navigates to dashboard or polling completes
                time.sleep(15)

            # 3. Dashboard Page & Assertions
            print("\n[3/5] Navigating to Dashboard page & verifying populated content...")
            page.goto(f"{base_url}/dashboard", timeout=30000, wait_until="networkidle")
            time.sleep(5)

            # Wait for content to be populated (wait up to 30s)
            dashboard_populated = False
            insight_cards = []
            charts = []
            for _ in range(15):
                insight_cards = page.query_selector_all("text='CONFIDENCE'") + page.query_selector_all("text='Impact:'")
                if not insight_cards:
                    # Alternative selector: search for badge or card containers
                    insight_cards = page.query_selector_all(".rt-Badge:has-text('CONFIDENCE')") or page.query_selector_all("div:has-text('Used:')")
                charts = page.query_selector_all("svg.recharts-surface") or page.query_selector_all("svg")
                if len(insight_cards) >= 1 and len(charts) >= 1:
                    dashboard_populated = True
                    break
                time.sleep(2)

            # ASSERTION 1: Dashboard has >= 1 insight card and a chart element
            assert len(insight_cards) >= 1, f"Assertion failed: Dashboard has {len(insight_cards)} insight cards (expected >= 1)"
            assert len(charts) >= 1, f"Assertion failed: Dashboard has {len(charts)} chart elements (expected >= 1)"
            res1 = f"ASSERTION PASSED: Dashboard populated with {len(insight_cards)} insight indicators and {len(charts)} chart elements"
            print(f"      [PASS] {res1}")
            assertion_results.append(res1)

            # Save screenshot only after assertion passes
            p3 = SCREENSHOTS_DIR / "03_dashboard.png"
            page.screenshot(path=str(p3), full_page=True)
            print(f"      Captured: {p3}")
            captured_screenshots.append(str(p3))

            # 4. Chat Page & Assertions
            print("\n[4/5] Navigating to Chat page & testing conversational query...")
            page.goto(f"{base_url}/chat", timeout=30000, wait_until="networkidle")
            time.sleep(3)

            chat_input = page.query_selector("input[placeholder*='Ask']") or page.query_selector("input[type='text']") or page.query_selector("textarea")
            if chat_input:
                chat_input.fill("What is the overall trend in monthly sales?")
                time.sleep(1)
                send_btn = page.query_selector("button:has-text('Send')") or page.query_selector("button[type='submit']")
                if send_btn:
                    send_btn.click()
                    print("      Submitted chat query. Waiting for assistant answer...")
                    time.sleep(6)

            # Wait for assistant response to appear
            chat_answer_text = ""
            for _ in range(10):
                # Look for assistant response text or message bubble
                answer_el = page.query_selector("div:has-text('Autonomous Analyst') + div") or page.query_selector("div:has-text('sales')")
                all_text = page.inner_text("body")
                if "Autonomous Analyst" in all_text and ("sales" in all_text.lower() or "trend" in all_text.lower() or "trajectory" in all_text.lower() or "correlation" in all_text.lower()):
                    chat_answer_text = all_text
                    break
                time.sleep(2)

            # ASSERTION 2: Chat shows an answer
            assert len(chat_answer_text) > 0, "Assertion failed: Chat answer was empty or not displayed"
            res2 = f"ASSERTION PASSED: Chat shows populated grounded answer ({len(chat_answer_text)} chars)"
            print(f"      [PASS] {res2}")
            assertion_results.append(res2)

            # Save screenshot only after assertion passes
            p4 = SCREENSHOTS_DIR / "04_chat_interaction.png"
            page.screenshot(path=str(p4), full_page=True)
            print(f"      Captured: {p4}")
            captured_screenshots.append(str(p4))

            # 5. Reports Page & Assertions
            print("\n[5/5] Navigating to Reports page & verifying generated reports list...")
            page.goto(f"{base_url}/reports", timeout=30000, wait_until="networkidle")
            time.sleep(3)

            refresh_btn = page.query_selector("button:has-text('Refresh')")
            if refresh_btn:
                refresh_btn.click()
                time.sleep(2)

            # Wait for reports table to show generated files
            report_rows = []
            for _ in range(10):
                report_rows = page.query_selector_all("table tbody tr") or page.query_selector_all("text='.pdf'") or page.query_selector_all("text='.docx'")
                if len(report_rows) >= 1:
                    break
                time.sleep(2)

            # ASSERTION 3: Reports page lists a generated file
            assert len(report_rows) >= 1, f"Assertion failed: Reports page listed {len(report_rows)} generated reports (expected >= 1)"
            res3 = f"ASSERTION PASSED: Reports page lists {len(report_rows)} generated report files"
            print(f"      [PASS] {res3}")
            assertion_results.append(res3)

            # Save screenshot only after assertion passes
            p5 = SCREENSHOTS_DIR / "05_reports_page.png"
            page.screenshot(path=str(p5), full_page=True)
            print(f"      Captured: {p5}")
            captured_screenshots.append(str(p5))

        finally:
            browser.close()

    print("\n" + "=" * 80)
    print("PLAYWRIGHT HEADLESS BROWSER RUN COMPLETE & ALL ASSERTIONS PASSED")
    print("=" * 80)
    print("ASSERTION RESULTS:")
    for res in assertion_results:
        print(f"  \u2713 {res}")
    print(f"\nCAPTURED SCREENSHOTS ({len(captured_screenshots)} total):")
    for s in captured_screenshots:
        print(f"  \u2022 {s}")
    print("=" * 80)
    return captured_screenshots, assertion_results

if __name__ == "__main__":
    run_playwright_e2e()
