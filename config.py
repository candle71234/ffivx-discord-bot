import os
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 設定線上下環境變數不同取得方式
def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"缺少環境變數：{name}")
    return value


def get_env_int(name: str, default: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        if default is None:
            raise RuntimeError(f"缺少環境變數：{name}")
        return default
    return int(raw)


TAIWAN_TZ = ZoneInfo("Asia/Taipei")

DISCORD_BOT_TOKEN = get_env("DISCORD_BOT_TOKEN")
REMINDER_CHANNEL_ID = get_env_int("REMINDER_CHANNEL_ID")
DAILY_ROUTINE_ROLE_ID = get_env_int("DAILY_ROUTINE_ROLE_ID")
WEEKLY_ROUTINE_ROLE_ID = get_env_int("WEEKLY_ROUTINE_ROLE_ID")

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SUBMARINE_DATA_FILE = DATA_DIR / "submarine_jobs.json"
FARM_DATA_FILE = DATA_DIR / "farm_data.json"
