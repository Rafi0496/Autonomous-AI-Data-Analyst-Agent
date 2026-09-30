"""Standalone verification script for Live LLM API calls (Gemini / Claude).

Usage:
  python scripts/test_live_llm.py [--provider gemini|claude] [--api-key KEY]
"""
from scripts.test_live_claude import run_live_test
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Live LLM Provider Integration (Claude / Gemini)")
    parser.add_argument("--provider", choices=["gemini", "claude", "heuristic"], help="LLM Provider")
    parser.add_argument("--api-key", help="API Key (never printed or logged)")
    args = parser.parse_args()
    run_live_test(args.provider, args.api_key)
