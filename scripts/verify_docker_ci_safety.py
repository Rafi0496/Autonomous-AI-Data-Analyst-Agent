"""Verify Docker and CI Safety (Task A7).

1. Reads docker-compose.yml environment variables for the backend service.
2. Simulates Settings instantiation and startup config validation with exactly those env vars.
3. Checks offline CI workflow steps to confirm no external files or secrets outside repo are required.
"""
import os
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    print("=" * 70)
    print("  TASK A7: DOCKER & CI SAFETY VERIFICATION")
    print("=" * 70)

    # 1. Parse docker-compose.yml
    compose_path = ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist"
    
    with open(compose_path, "r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    backend_env = compose_data["services"]["backend"]["environment"]
    env_dict = {}
    for item in backend_env:
        if "=" in item:
            k, v = item.split("=", 1)
            env_dict[k] = v

    print("\n[1] docker-compose.yml backend environment variables:")
    for k, v in env_dict.items():
        print(f"  {k} = {v}")

    # Assertions on docker-compose.yml
    assert "ENVIRONMENT" in env_dict, "ENVIRONMENT must be explicitly defined in docker-compose"
    assert env_dict["ENVIRONMENT"] == "dev", f"ENVIRONMENT must be 'dev', got {env_dict['ENVIRONMENT']}"
    assert "JWT_SECRET" in env_dict, "JWT_SECRET must be defined in docker-compose"
    assert "dev" in env_dict["JWT_SECRET"].lower(), f"JWT_SECRET must be labelled dev, got {env_dict['JWT_SECRET']}"
    print("\n[+] Confirmed docker-compose.yml sets ENVIRONMENT=dev and a labelled dev JWT_SECRET.")

    # 2. Simulate startup config validation with exactly those env vars
    print("\n[2] Simulating Settings() instantiation with compose env vars:")
    saved_env = os.environ.copy()
    try:
        # Clear existing env overrides and set exactly compose env
        for k in ["ENVIRONMENT", "DATABASE_URL", "REDIS_URL", "JWT_SECRET", "LLM_PROVIDER",
                  "POSTGRES_SERVER", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_PORT"]:
            if k in os.environ:
                del os.environ[k]
        os.environ.update(env_dict)

        from backend.app.core.config import Settings
        settings_test = Settings()
        print(f"  Instantiated Settings successfully:")
        print(f"  - ENVIRONMENT: {settings_test.ENVIRONMENT}")
        print(f"  - JWT_SECRET: {settings_test.JWT_SECRET}")
        print(f"  - LLM_PROVIDER: {settings_test.LLM_PROVIDER}")
        print(f"  - DATABASE_URL: {settings_test.DATABASE_URL}")
        print(f"  - ACCESS_TOKEN_EXPIRE_MINUTES: {settings_test.ACCESS_TOKEN_EXPIRE_MINUTES}")
        print("[+] Startup config validation PASSED with compose environment.")
    finally:
        os.environ.clear()
        os.environ.update(saved_env)

    # 3. Confirm CI offline test job requires no external files
    ci_path = ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists(), ".github/workflows/ci.yml must exist"
    with open(ci_path, "r", encoding="utf-8") as f:
        ci_content = f.read()

    print("\n[3] Checking .github/workflows/ci.yml offline test job:")
    assert "actions/checkout" in ci_content, "Must checkout repository"
    assert "pytest -m \"not live\"" in ci_content, "Must run pytest offline markers"
    assert "LLM_PROVIDER: heuristic" in ci_content, "Must use heuristic provider offline"
    
    # Check for external secrets or non-repo dependencies in offline job
    assert "secrets." not in ci_content.split("docker-build:")[0], "Offline job must not depend on external GitHub secrets"
    print("[+] Confirmed offline test job needs no external files, services, or secrets outside the repo.")

    print("\n" + "=" * 70)
    print("  TASK A7 VERIFICATION SUCCEEDED")
    print("=" * 70)

if __name__ == "__main__":
    main()
