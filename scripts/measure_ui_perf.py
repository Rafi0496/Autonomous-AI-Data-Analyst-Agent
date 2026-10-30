"""Comprehensive Playwright UI Performance Measurement Script for Reflex Frontend."""
import json
import os
import sys
import time
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def run_performance_audit() -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "page_navigation_ms": {},
        "button_click_ms": 0.0,
        "sidebar_toggle_ms": 0.0,
        "theme_toggle_ms": 0.0,
        "chat_typing": {},
        "scroll_fps": {},
        "ws_events": {
            "sent_count": 0,
            "received_count": 0,
        },
    }

    ws_frames_sent = []
    ws_frames_recv = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        def on_websocket(ws):
            def on_frame_sent(payload):
                ws_frames_sent.append({"time": time.perf_counter(), "payload": str(payload)[:100]})
            def on_frame_recv(payload):
                ws_frames_recv.append({"time": time.perf_counter(), "payload": str(payload)[:100]})
            ws.on("framesent", on_frame_sent)
            ws.on("framereceived", on_frame_recv)

        page.on("websocket", on_websocket)

        # 1. Warm-up & Initial Load
        print("[1/7] Loading Home page...", flush=True)
        t0 = time.perf_counter()
        page.goto(f"{BASE_URL}/", wait_until="load", timeout=30000)
        page.wait_for_selector(".landing-page-container", timeout=20000)
        time.sleep(1.0) # allow initial ws handshake
        results["page_navigation_ms"]["home"] = round((time.perf_counter() - t0) * 1000, 2)
        print(f"      Home loaded in {results['page_navigation_ms']['home']} ms", flush=True)

        # 2. Page Navigation Timings across all 8 routes
        routes = [
            ("upload", "/upload"),
            ("run", "/run"),
            ("dashboard", "/dashboard"),
            ("chat", "/chat"),
            ("reports", "/reports"),
            ("settings", "/settings"),
            ("login", "/login"),
            ("home_return", "/"),
        ]

        print("[2/7] Testing route navigation...", flush=True)
        for name, route in routes:
            t_nav = time.perf_counter()
            page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)
            nav_ms = (time.perf_counter() - t_nav) * 1000
            results["page_navigation_ms"][name] = round(nav_ms, 2)
            print(f"      Navigated to {route} in {results['page_navigation_ms'][name]} ms", flush=True)
            time.sleep(0.3)

        # 3. Sidebar Toggle Latency on an operational page (/dashboard)
        print("[3/7] Testing sidebar toggle latency...", flush=True)
        page.goto(f"{BASE_URL}/dashboard", wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.0)

        sidebar_btn = page.locator("button[aria-label*='sidebar'], button[aria-label*='Sidebar']").first
        if sidebar_btn.count() > 0:
            initial_collapsed = page.evaluate("() => document.querySelector('.app-sidebar')?.classList.contains('collapsed')")
            t_sb = time.perf_counter()
            sidebar_btn.click()
            try:
                page.wait_for_function(
                    f"(expected) => (document.querySelector('.app-sidebar')?.classList.contains('collapsed')) !== expected",
                    arg=initial_collapsed,
                    timeout=8000
                )
                sb_ms = (time.perf_counter() - t_sb) * 1000
                results["sidebar_toggle_ms"] = round(sb_ms, 2)
                print(f"      Sidebar toggled in {results['sidebar_toggle_ms']} ms", flush=True)
            except Exception as e:
                print(f"      Sidebar toggle timed out: {e}", flush=True)
                results["sidebar_toggle_ms"] = 9999.0

        # 4. Theme Toggle Latency
        print("[4/7] Testing theme toggle latency...", flush=True)
        theme_btn = page.locator("div[title*='Toggle'], div[title*='toggle']").first
        if theme_btn.count() > 0:
            initial_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme') || (document.body.classList.contains('theme-light') ? 'light' : 'dark')")
            t_th = time.perf_counter()
            theme_btn.click()
            try:
                page.wait_for_function(
                    f"(init) => (document.documentElement.getAttribute('data-theme') || (document.body.classList.contains('theme-light') ? 'light' : 'dark')) !== init",
                    arg=initial_theme,
                    timeout=8000
                )
                th_ms = (time.perf_counter() - t_th) * 1000
                results["theme_toggle_ms"] = round(th_ms, 2)
                print(f"      Theme toggled in {results['theme_toggle_ms']} ms", flush=True)
            except Exception as e:
                print(f"      Theme toggle timed out: {e}", flush=True)
                results["theme_toggle_ms"] = 9999.0

        # 5. Typing Latency in Chat Input
        print("[5/7] Testing typing latency in chat input...", flush=True)
        page.goto(f"{BASE_URL}/chat", wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.0)

        test_text = "What are the insights?"
        chat_box = page.locator("#chat-input-textarea")
        if chat_box.count() > 0:
            chat_box.click()
            ws_sent_before_type = len(ws_frames_sent)
            t_type_start = time.perf_counter()
            char_latencies = []
            for ch in test_text:
                tc0 = time.perf_counter()
                chat_box.type(ch, delay=15)
                char_latencies.append((time.perf_counter() - tc0) * 1000)

            total_type_ms = (time.perf_counter() - t_type_start) * 1000
            ws_sent_during_type = len(ws_frames_sent) - ws_sent_before_type

            results["chat_typing"] = {
                "total_ms": round(total_type_ms, 2),
                "char_count": len(test_text),
                "avg_ms_per_char": round(sum(char_latencies) / len(char_latencies), 2),
                "max_ms_per_char": round(max(char_latencies), 2),
                "ws_events_fired": ws_sent_during_type,
            }
            print(f"      Typed {len(test_text)} chars in {total_type_ms:.1f} ms ({results['chat_typing']['avg_ms_per_char']} ms/char, {ws_sent_during_type} WS events)", flush=True)

        # 6. Button Click to Visual Response
        print("[6/7] Testing button click response...", flush=True)
        page.goto(f"{BASE_URL}/settings", wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.0)
        auth_btn = page.locator("button:has-text('Sign In')").first
        if auth_btn.count() > 0:
            t_btn = time.perf_counter()
            auth_btn.click()
            try:
                page.wait_for_selector("[role='dialog']", timeout=8000)
                btn_ms = (time.perf_counter() - t_btn) * 1000
                results["button_click_ms"] = round(btn_ms, 2)
                print(f"      Button click responded in {results['button_click_ms']} ms", flush=True)
            except Exception as e:
                print(f"      Button click timed out: {e}", flush=True)
                results["button_click_ms"] = 9999.0

        # 7. Scroll FPS Measurement on Home page
        print("[7/7] Measuring scroll FPS...", flush=True)
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.0)

        fps_data = page.evaluate("""() => {
            return new Promise((resolve) => {
                let frameDeltas = [];
                let lastTime = performance.now();
                let scrollCount = 0;
                
                function frame(now) {
                    let delta = now - lastTime;
                    lastTime = now;
                    frameDeltas.push(delta);
                    window.scrollBy(0, 18);
                    scrollCount++;
                    if (scrollCount < 60) {
                        requestAnimationFrame(frame);
                    } else {
                        window.scrollTo(0, 0);
                        let fpsList = frameDeltas.slice(2).map(d => 1000 / d);
                        let avgFps = fpsList.reduce((a, b) => a + b, 0) / fpsList.length;
                        let minFps = Math.min(...fpsList);
                        let dropped = fpsList.filter(f => f < 50).length;
                        resolve({
                            avg_fps: Math.round(avgFps * 10) / 10,
                            min_fps: Math.round(minFps * 10) / 10,
                            dropped_frames_under_50: dropped,
                            total_frames_sampled: fpsList.length
                        });
                    }
                }
                requestAnimationFrame(frame);
            });
        }""")
        results["scroll_fps"] = fps_data
        print(f"      Scroll FPS: Avg={fps_data.get('avg_fps')}, Min={fps_data.get('min_fps')}, Dropped={fps_data.get('dropped_frames_under_50')}", flush=True)

        results["ws_events"]["sent_count"] = len(ws_frames_sent)
        results["ws_events"]["received_count"] = len(ws_frames_recv)
        print(f"Total WS frames: {len(ws_frames_sent)} sent, {len(ws_frames_recv)} received", flush=True)

        browser.close()

    return results

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    is_smoke_test = "--smoke-test" in sys.argv or mode == "smoke-test"
    print(f"Running performance audit in [{mode}] mode (Smoke test: {is_smoke_test})...", flush=True)
    metrics = run_performance_audit()
    print("--- METRICS RESULT JSON START ---", flush=True)
    print(json.dumps(metrics, indent=2), flush=True)
    print("--- METRICS RESULT JSON END ---", flush=True)

    if is_smoke_test:
        print("\n--- PERFORMANCE SMOKE TEST VERIFICATION ---", flush=True)
        failures = []

        sb_toggle = metrics.get("sidebar_toggle_ms", 9999)
        if sb_toggle > 150.0:
            failures.append(f"Sidebar toggle latency too high: {sb_toggle}ms (Target: <150ms)")
        else:
            print(f" PASS: Sidebar toggle: {sb_toggle}ms (<150ms)", flush=True)

        th_toggle = metrics.get("theme_toggle_ms", 9999)
        if th_toggle > 100.0:
            failures.append(f"Theme toggle latency too high: {th_toggle}ms (Target: <100ms)")
        else:
            print(f" PASS: Theme toggle: {th_toggle}ms (<100ms)", flush=True)

        typing_ws = metrics.get("chat_typing", {}).get("ws_events_fired", 999)
        if typing_ws > 1:
            failures.append(f"Typing fired excessive WebSocket events: {typing_ws} events (Target: <=1)")
        else:
            print(f" PASS: Typing WS events: {typing_ws} events (<=1)", flush=True)

        avg_fps = metrics.get("scroll_fps", {}).get("avg_fps", 0)
        if avg_fps < 55.0:
            failures.append(f"Scroll FPS too low: {avg_fps} FPS (Target: >=55 FPS)")
        else:
            print(f" PASS: Scroll FPS: {avg_fps} FPS (>=55 FPS)", flush=True)

        dropped = metrics.get("scroll_fps", {}).get("dropped_frames_under_50", 999)
        if dropped > 3:
            failures.append(f"Too many dropped frames: {dropped} dropped (Target: <=3)")
        else:
            print(f" PASS: Dropped scroll frames: {dropped} (<=3)", flush=True)

        if failures:
            print(f"\n❌ SMOKE TEST FAILED with {len(failures)} violations:", flush=True)
            for f in failures:
                print(f"  - {f}", flush=True)
            sys.exit(1)
        else:
            print("\n✅ ALL PERFORMANCE TARGETS PASSED BUTTERY-SMOOTH!", flush=True)
            sys.exit(0)
