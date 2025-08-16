import asyncio
import subprocess
import sys
import os
import yaml
from datetime import datetime, timedelta

# Paths
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "main.py")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def get_seconds_until_next_run(target_hour, target_minute):
    now = datetime.now()
    next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()

async def run_daily_at(hour: int, minute: int):
    while True:
        # ⏳ Wait until the *next* scheduled time BEFORE running
        seconds_to_wait = get_seconds_until_next_run(hour, minute)
        run_time = datetime.now() + timedelta(seconds=seconds_to_wait)
        print(f"🕒 Waiting until: {run_time.strftime('%Y-%m-%d %H:%M:%S')}")
        await asyncio.sleep(seconds_to_wait)

        # 🚀 Run main.py
        print(f"🚀 Starting run at {datetime.now().isoformat()}")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            SCRIPT_PATH,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        print(f"✅ Finished run at {datetime.now().isoformat()} with exit code {process.returncode}")
        if stdout:
            print("📤 Output:\n", stdout.decode())
        if stderr:
            print("📥 Logs from stderr (may include warnings/errors):\n", stderr.decode())

        # 💤 Sleep until the next day’s run
        print("📆 Scheduling next run...")
        # Loop will calculate next day's delay

if __name__ == "__main__":
    config = load_config()
    schedule = config.get("schedule", {})
    hour = schedule.get("hour", 6)
    minute = schedule.get("minute", 0)

    asyncio.run(run_daily_at(hour, minute))
