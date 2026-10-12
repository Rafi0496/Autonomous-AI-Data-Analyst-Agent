import os
import sys
import time
import json
import math
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path("reports/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("home", "/"),
    ("dashboard", "/dashboard"),
    ("run", "/run"),
    ("chat", "/chat"),
    ("upload", "/upload"),
    ("reports", "/reports"),
    ("settings", "/settings"),
    ("login", "/login"),
]

def rgb_to_linear(val):
    c = val / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4

def get_luminance(hex_code):
    hex_clean = hex_code.lstrip("#")
    r = int(hex_clean[0:2], 16)
    g = int(hex_clean[2:4], 16)
    b = int(hex_clean[4:6], 16)
    r_lin = rgb_to_linear(r)
    g_lin = rgb_to_linear(g)
    b_lin = rgb_to_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def calculate_contrast_ratio(hex1, hex2):
    lum1 = get_luminance(hex1)
    lum2 = get_luminance(hex2)
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)

def run_verification():
    print("=== Starting Comprehensive Frontend Polish Verification ===")
    
    # 1. Color Contrast Ratios (Mathematical WCAG 2.1)
    print("\n[1] Calculating Exact WCAG 2.1 Contrast Ratios:")
    color_pairs = [
        ("Light Theme - Body Text (#1E293B) on Surface (#EFEEEB)", "#1E293B", "#EFEEEB", 4.5),
        ("Light Theme - Body Text (#1E293B) on Base (#EAE9E5)", "#1E293B", "#EAE9E5", 4.5),
        ("Light Theme - Secondary/Muted (#475569) on Surface (#EFEEEB)", "#475569", "#EFEEEB", 4.5),
        ("Light Theme - Primary Button Text (#FFFFFF) on Muted Slate-Teal (#4F7C82)", "#FFFFFF", "#4F7C82", 4.5),
        ("Light Theme - Primary Hover (#FFFFFF) on Darker Slate-Teal (#3D6368)", "#FFFFFF", "#3D6368", 4.5),
        ("Light Theme - Large Headings (#0F172A) on Base (#EAE9E5)", "#0F172A", "#EAE9E5", 3.0),
        ("Light Theme - Sage Status Text (#224D33) on Surface (#EFEEEB)", "#224D33", "#EFEEEB", 4.5),
        ("Dark Theme - Body Text (#F1F5F9) on Base (#1B2230)", "#F1F5F9", "#1B2230", 4.5),
        ("Dark Theme - Body Text (#F1F5F9) on Surface (#202838)", "#F1F5F9", "#202838", 4.5),
        ("Dark Theme - Primary Action Text (#121B24) on Light Slate-Teal (#7FB3B8)", "#121B24", "#7FB3B8", 4.5),
        ("Dark Theme - Muted Text (#94A3B8) on Surface (#202838)", "#94A3B8", "#202838", 4.5),
    ]

    measured_contrasts = {}
    for label, fg, bg, req in color_pairs:
        ratio = calculate_contrast_ratio(fg, bg)
        passed = ratio >= req
        measured_contrasts[label] = {
            "foreground": fg,
            "background": bg,
            "ratio": round(ratio, 2),
            "required": req,
            "passed": passed
        }
        status_str = "PASS" if passed else "FAIL"
        print(f"  - {label}: {ratio:.2f}:1 (Target: >={req}:1) -> {status_str}")

    # 2. Playwright Automated Visual & Axe Audit
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        
        # Test configurations
        viewports = [
            (1920, 1080, "1920"),
            (1280, 800, "1280"),
        ]
        
        # Page screenshots and theme switching
        for width, height, vp_label in viewports:
            for theme_name, is_dark in [("light", False), ("dark", True)]:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    color_scheme="dark" if is_dark else "light"
                )
                page = context.new_page()

                for page_name, path in PAGES:
                    target_url = f"http://localhost:3000{path}"
                    try:
                        page.goto(target_url, wait_until="networkidle", timeout=15000)
                    except Exception:
                        page.goto(target_url, timeout=15000)
                    
                    time.sleep(1) # Let reflex hydration and animations settle

                    # Ensure proper theme is active
                    if is_dark:
                        page.evaluate("""
                            document.documentElement.setAttribute('data-theme', 'dark');
                            document.body.setAttribute('data-theme', 'dark');
                            document.documentElement.classList.add('dark', 'theme-dark');
                            document.documentElement.classList.remove('light', 'theme-light');
                            document.querySelectorAll('.theme-light').forEach(el => {
                                el.classList.remove('theme-light');
                                el.classList.add('theme-dark');
                            });
                        """)
                    else:
                        page.evaluate("""
                            document.documentElement.setAttribute('data-theme', 'light');
                            document.body.setAttribute('data-theme', 'light');
                            document.documentElement.classList.add('light', 'theme-light');
                            document.documentElement.classList.remove('dark', 'theme-dark');
                            document.querySelectorAll('.theme-dark').forEach(el => {
                                el.classList.remove('theme-dark');
                                el.classList.add('theme-light');
                            });
                        """)
                    
                    time.sleep(0.5)

                    # Save screenshot
                    img_path = (SCREENSHOTS_DIR / f"{page_name}_{theme_name}_{vp_label}.png").resolve()
                    try:
                        page.screenshot(path=str(img_path), full_page=False)
                        print(f"  [Screenshot] {img_path.name}")
                    except Exception as e:
                        time.sleep(0.5)
                        page.screenshot(path=str(img_path), full_page=False)
                        print(f"  [Screenshot (retry)] {img_path.name}")
                
                context.close()

        # 3. Sidebar Specific Verification (Expanded, Collapsed Rail, Mid-Transition)
        print("\n[2] Capturing Sidebar States:")
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
        sb_page = ctx.new_page()
        sb_page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
        time.sleep(1)

        # 3a. Expanded (280px)
        sb_page.evaluate("const sb = document.querySelector('.app-sidebar'); if (sb) { sb.style.width = '280px'; sb.classList.remove('collapsed'); }")
        time.sleep(0.3)
        expanded_path = (SCREENSHOTS_DIR / "sidebar_expanded_280px.png").resolve()
        sb_page.screenshot(path=str(expanded_path))
        print(f"  [Screenshot] {expanded_path.name}")

        # 3b. Mid-transition (160px width)
        sb_page.evaluate("const sb = document.querySelector('.app-sidebar'); if (sb) { sb.style.width = '160px'; }")
        time.sleep(0.2)
        mid_path = (SCREENSHOTS_DIR / "sidebar_mid_transition.png").resolve()
        sb_page.screenshot(path=str(mid_path))
        print(f"  [Screenshot] {mid_path.name}")
        
        # 3c. Collapsed Rail (72px)
        sb_page.evaluate("const sb = document.querySelector('.app-sidebar'); if (sb) { sb.style.width = '72px'; sb.classList.add('collapsed'); }")
        time.sleep(0.3)
        collapsed_path = (SCREENSHOTS_DIR / "sidebar_collapsed_rail_72px.png").resolve()
        sb_page.screenshot(path=str(collapsed_path))
        print(f"  [Screenshot] {collapsed_path.name}")
        ctx.close()

        # 4. Mobile Drawer (<900px, e.g. 768px and 375px)
        print("\n[3] Capturing Mobile Drawer:")
        mobile_ctx = browser.new_context(viewport={"width": 768, "height": 1024})
        mobile_page = mobile_ctx.new_page()
        mobile_page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
        time.sleep(1)

        # Closed mobile
        mob_closed_path = (SCREENSHOTS_DIR / "mobile_768_closed.png").resolve()
        mobile_page.screenshot(path=str(mob_closed_path))
        print(f"  [Screenshot] {mob_closed_path.name}")

        # Open mobile drawer with scrim
        mobile_page.evaluate("""
            const sb = document.querySelector('.app-sidebar');
            if (sb) { sb.classList.add('mobile-open'); sb.style.transform = 'translateX(0)'; }
            const sc = document.querySelector('.sidebar-scrim');
            if (sc) { sc.classList.add('visible'); sc.style.opacity = '1'; }
        """)
        time.sleep(0.5)
        mob_open_path = (SCREENSHOTS_DIR / "mobile_768_drawer_open.png").resolve()
        mobile_page.screenshot(path=str(mob_open_path))
        print(f"  [Screenshot] {mob_open_path.name}")

        mobile_ctx.close()

        # 5. Search Bar & Inset Box Focus Check
        print("\n[4] Capturing Search Bar Detail (Light & Dark):")
        for mode in ["light", "dark"]:
            search_ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            sp = search_ctx.new_page()
            sp.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
            time.sleep(1)
            if mode == "dark":
                sp.evaluate("document.documentElement.classList.add('dark'); document.documentElement.classList.remove('light');")
                time.sleep(0.5)
            
            # Focus search bar
            search_input = sp.locator("input[placeholder='Search runs, datasets...'], input[type='text']").first
            if search_input.count() > 0:
                search_input.focus()
                time.sleep(0.3)
                search_shot = (SCREENSHOTS_DIR / f"search_input_focused_{mode}.png").resolve()
                search_input.screenshot(path=str(search_shot))
                print(f"  [Screenshot] {search_shot.name}")
            search_ctx.close()

        # 6. Axe-Core Accessibility Check
        print("\n[5] Running Axe-core Accessibility & Contrast Check:")
        axe_ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
        axe_page = axe_ctx.new_page()
        axe_page.goto("http://localhost:3000/dashboard", wait_until="networkidle", timeout=15000)
        time.sleep(1)

        from axe_playwright_python.sync_playwright import Axe
        axe = Axe()
        results = axe.run(axe_page)
        violations = results.violations_count
        print(f"  Axe-core Violations on Dashboard: {violations}")
        
        axe_ctx.close()
        browser.close()

    # Save summary report
    report_data = {
        "measured_contrasts": measured_contrasts,
        "axe_violations_count": violations,
        "screenshots_count": len(list(SCREENSHOTS_DIR.glob("*.png"))),
    }
    with open("reports/verification_summary.json", "w") as f:
        json.dump(report_data, f, indent=2)

    print("\n=== Verification Completed Successfully ===")

if __name__ == "__main__":
    run_verification()
