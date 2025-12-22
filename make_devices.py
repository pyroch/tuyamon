import subprocess
import sys

def run_wizard():
    print("Running tinytuya wizard automatically...")

    result = subprocess.run(
        [sys.executable, '-m', 'tinytuya', 'wizard', '-yes', '30'],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    print(result.stdout)
    print(result.stderr)

    print("Wizard finished")
    exit(0)

run_wizard()