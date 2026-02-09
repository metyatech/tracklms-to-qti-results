import subprocess
import sys
from pathlib import Path


def run_command(command, description):
    print(f"--- Running {description} ---")
    print(f"Command: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {description} failed.")
        print(e.stdout)
        print(e.stderr)
        return False


def main():
    success = True

    # 1. Format check
    if not run_command(["python", "-m", "ruff", "format", "--check", "."], "Ruff format check"):
        success = False

    # 2. Lint check
    if not run_command(["python", "-m", "ruff", "check", "."], "Ruff lint check"):
        success = False

    # 3. Type check
    if not run_command(["python", "-m", "pyright", "src"], "Pyright type check"):
        success = False

    # 4. Tests
    if not run_command(["python", "-m", "unittest", "discover", "-s", "tests"], "Unit tests"):
        success = False

    # 5. Build check
    if not run_command(["python", "-m", "build"], "Build check"):
        success = False

    # 6. Dependency audit
    # Only run if requirements-dev.txt exists
    if Path("requirements-dev.txt").exists():
        if not run_command(
            ["python", "-m", "pip_audit", "-r", "requirements-dev.txt"], "Dependency audit"
        ):
            success = False

    if success:
        print("--- All verification checks passed! ---")
        sys.exit(0)
    else:
        print("--- Verification failed. ---")
        sys.exit(1)


if __name__ == "__main__":
    main()
