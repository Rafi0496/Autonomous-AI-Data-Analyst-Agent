import json
import time
from playwright.sync_api import sync_playwright

FRONTEND_URL = "https://autonomous-ai-data-analyst-frontend.onrender.com"

print(f"Tracing performance on: {FRONTEND_URL}")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    # Capture performance metrics via CDP
    client = context.new_cdp_session(page)
    client.send("Performance.enable")

    # Trace navigation from home to upload, run, dashboard, chat, settings
    routes = ["/", "/upload", "/run", "/dashboard", "/chat", "/reports", "/settings"]
    timings = {}
    long_tasks = []

    # Inject PerformanceObserver for long tasks
    page.add_init_script("""
        window.__longTasks = [];
        const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                window.__longTasks.push({
                    name: entry.name,
                    duration: entry.duration,
                    startTime: entry.startTime
                });
            }
        });
        observer.observe({entryTypes: ['longtask']});
    """)

    for route in routes:
        t0 = time.perf_counter()
        page.goto(f"{FRONTEND_URL}{route}", wait_until="networkidle", timeout=30000)
        nav_duration = (time.perf_counter() - t0) * 1000
        timings[route] = round(nav_duration, 2)
        time.sleep(1)

    # Collect long tasks and CDP performance metrics
    cdp_metrics = client.send("Performance.getMetrics")
    metrics_dict = {m["name"]: m["value"] for m in cdp_metrics["metrics"]}

    captured_long_tasks = page.evaluate("window.__longTasks || []")

    results = {
        "route_timings_ms": timings,
        "cdp_metrics": {
            "TaskDuration": metrics_dict.get("TaskDuration", 0),
            "ScriptDuration": metrics_dict.get("ScriptDuration", 0),
            "LayoutDuration": metrics_dict.get("LayoutDuration", 0),
            "RecalcStyleDuration": metrics_dict.get("RecalcStyleDuration", 0),
            "JSHeapUsedSizeMB": round(metrics_dict.get("JSHeapUsedSize", 0) / (1024 * 1024), 2),
            "Nodes": metrics_dict.get("Nodes", 0),
            "LayoutCount": metrics_dict.get("LayoutCount", 0)
        },
        "long_tasks_over_50ms_count": len([t for t in captured_long_tasks if t.get("duration", 0) > 50]),
        "top_long_tasks": sorted(captured_long_tasks, key=lambda x: x.get("duration", 0), reverse=True)[:5]
    }

    print("\n--- PERFORMANCE TRACE RESULTS ---")
    print(json.dumps(results, indent=2))
    
    with open("data/demo_outputs/perf_trace.json", "w") as f:
        json.dump(results, f, indent=2)

    browser.close()
