import json
from datetime import datetime, timedelta

from config import FARM_DATA_FILE, TAIWAN_TZ
from farm_seeds import SEEDS, CROP_CATEGORIES

def create_farm_slot(slot_id: int) -> dict:
    return {
        "slot_id": slot_id,
        "blocked": slot_id == 5,

        "seed_key": None,
        "crop": None,
        "category": None,

        "planted_at": None,
        "watered_at": None,
        "fertilized_at": None,
        "mature_at": None,

        "care_hours": None,
        "notified": False,

        # 澆水提醒旗標
        "care_remind_24h_sent": False,
        "care_remind_urgent_sent": False,
    }


def create_new_farm(guild_id: int) -> dict:
    return {
        "guild_id": guild_id,
        "slots": {
            str(slot_id): create_farm_slot(slot_id)
            for slot_id in range(1, 10)
        }
    }


def reset_slot(slot: dict):
    slot["seed_key"] = None
    slot["crop"] = None
    slot["category"] = None

    slot["planted_at"] = None
    slot["watered_at"] = None
    slot["fertilized_at"] = None
    slot["mature_at"] = None

    slot["care_hours"] = None
    slot["notified"] = False

    slot["care_remind_24h_sent"] = False
    slot["care_remind_urgent_sent"] = False


def load_farm_data() -> dict:
    if not FARM_DATA_FILE.exists():
        return {}

    try:
        with open(FARM_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[farm] 載入資料失敗: {e}")
        return {}


def save_farm_data(data: dict):
    try:
        with open(FARM_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[farm] 儲存資料失敗: {e}")

# 抓取作物種類
def get_category_choices() -> list[tuple[str, str]]:
    return [(label, key) for key, label in CROP_CATEGORIES.items()]

# 依分類取得作物選單
def get_crop_choices_by_category(category_key: str) -> list[tuple[str, str]]:
    choices = []

    for crop_key, crop in SEEDS.items():
        if crop["category"] != category_key:
            continue

        label = f"{crop['name']}（{crop_key}）"
        choices.append((label, crop_key))

    return choices



# 抓取單一格子資料
def get_slot_by_id(farm: dict, slot_id: int) -> dict | None:
    return farm["slots"].get(str(slot_id))


def get_slot_status_by_id(guild_id: int, slot_id: int) -> tuple[bool, str, dict | None]:
    farm = get_or_create_guild_farm(guild_id)
    slot = get_slot_by_id(farm, slot_id)

    if slot is None:
        return False, "找不到這個格子。", None

    if slot["blocked"]:
        return False, "這個位置不能操作。", slot

    if not slot.get("crop"):
        return False, "這個格子目前沒有作物。", slot

    return True, get_slot_status(slot), slot



def get_or_create_guild_farm(guild_id: int) -> dict:
    data = load_farm_data()
    guild_id_str = str(guild_id)

    if guild_id_str not in data:
        data[guild_id_str] = create_new_farm(guild_id)
        save_farm_data(data)

    return data[guild_id_str]


def update_guild_farm(guild_id: int, farm: dict):
    data = load_farm_data()
    data[str(guild_id)] = farm
    save_farm_data(data)


def get_crop_list_text() -> str:
    lines = []

    for crop_key, crop in SEEDS.items():
        care_text = "--" if crop["care_hours"] is None else f'{crop["care_hours"]} 小時'
        lines.append(
            f"{crop['name']}（{crop_key}）｜分類：{crop['category']}｜成熟 {crop['grow_hours']} 小時｜枯萎 {care_text}"
        )

    return "\n".join(lines)


def get_crop_list_text_by_category(category_key: str | None = None) -> str:
    lines = []

    for crop_key, crop in SEEDS.items():
        if category_key and crop["category"] != category_key:
            continue

        care_text = "--" if crop["care_hours"] is None else f'{crop["care_hours"]} 小時'
        lines.append(
            f"{crop['name']}（{crop_key}）｜成熟 {crop['grow_hours']} | 枯萎 {care_text}"
        )

    if not lines:
        return "這個分類目前沒有作物。"

    return "\n".join(lines)





def get_category_label(category_key: str) -> str:
    return CROP_CATEGORIES.get(category_key, category_key)


def get_crop_lines(category_key: str | None = None) -> list[str]:
    """
    取得作物列表行文字
    category_key = None 時回傳全部
    """
    lines = []

    for crop_key, crop in SEEDS.items():
        if category_key and crop["category"] != category_key:
            continue

        category_label = get_category_label(crop["category"])
        care_text = "--" if crop["care_hours"] is None else f'{crop["care_hours"]} 小時'

        lines.append(
            f"**{crop['name']}**\n"
            f"`{crop_key}`｜成熟：{crop['grow_hours']} 小時｜枯萎：{care_text}"
        )

    return lines

def crop_matches_category(crop_key: str, category_key: str | None) -> bool:
    """
    檢查 crop_key 是否屬於指定分類。
    category_key 為 None 時，一律視為合法。
    """
    if category_key is None:
        return True

    crop = SEEDS.get(crop_key)
    if crop is None:
        return False

    return crop.get("category") == category_key


def get_crop_lines_by_category(category_key: str) -> list[str]:
    """
    舊函式保留，內部直接轉給新函式
    """
    return get_crop_lines(category_key)


# 取得作物選項，顯示中文
def get_crop_choices() -> list[tuple[str, str]]:
    """回傳作物清單：(顯示名稱, crop_key)"""
    choices = []

    for crop_key, crop in SEEDS.items():
        label = f"{crop['name']}（{crop_key}）"
        choices.append((label, crop_key))

    return choices


# 解析格子輸入 支援同時輸入多筆
def parse_slot_input(target: str) -> tuple[bool, list[int] | str]:
    """
    解析格子輸入：
    - all
    - 1
    - 1246
    - 1,2,4,6
    - 1 2 4 6
    """
    target = target.strip().lower()

    if target == "all":
        return True, [1, 2, 3, 4, 6, 7, 8, 9]

    # 移除逗號與空白
    cleaned = target.replace(",", "").replace(" ", "")

    if not cleaned:
        return False, "請輸入格子編號。"

    if not cleaned.isdigit():
        return False, "格子格式錯誤，請輸入如 1、1246、1,2,4,6 或 all。"

    slots = []
    for ch in cleaned:
        slot_id = int(ch)
        if slot_id not in [1, 2, 3, 4, 6, 7, 8, 9]:
            return False, f"格子 {slot_id} 不可用。可用格子為 1,2,3,4,6,7,8,9。"
        if slot_id not in slots:
            slots.append(slot_id)

    return True, slots


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_wither_deadline(slot: dict) -> datetime | None:
    care_hours = slot.get("care_hours")
    if care_hours is None:
        return None

    watered_at = parse_iso_datetime(slot.get("watered_at"))
    planted_at = parse_iso_datetime(slot.get("planted_at"))

    base_time = watered_at or planted_at
    if base_time is None:
        return None

    return base_time + timedelta(hours=care_hours)


def get_slot_status(slot: dict) -> str:
    if slot["blocked"]:
        return "blocked"

    if not slot.get("crop"):
        return "empty"

    now = datetime.now(TAIWAN_TZ)

    # 先判斷是否枯萎
    wither_deadline = get_wither_deadline(slot)
    if wither_deadline is not None and now >= wither_deadline:
        return "withered"

    # 再判斷是否成熟
    mature_at = parse_iso_datetime(slot.get("mature_at"))
    if mature_at is not None and now >= mature_at:
        return "mature"

    return "growing"


def format_time_remaining(target_time_str: str | None) -> str:
    target_time = parse_iso_datetime(target_time_str)
    if target_time is None:
        return "--"

    now = datetime.now(TAIWAN_TZ)
    delta = target_time - now
    total_seconds = int(delta.total_seconds())

    if total_seconds <= 0:
        return "0分"

    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)

    if days > 0:
        return f"{days}天{hours}小時"
    if hours > 0:
        return f"{hours}小時{minutes}分"
    return f"{minutes}分"


def get_farm_slot_display(slot: dict) -> str:
    status = get_slot_status(slot)

    if status == "blocked":
        return "X 稻草人"

    if status == "empty":
        return f'{slot["slot_id"]} 空地'

    if status == "withered":
        return f'{slot["slot_id"]} ☠️{slot["crop"]}'

    if status == "mature":
        return f'{slot["slot_id"]} ✅{slot["crop"]}'

    remaining = format_time_remaining(slot.get("mature_at"))
    return f'{slot["slot_id"]} 🌱{slot["crop"]}({remaining})'


def render_farm_grid(farm: dict) -> str:
    slots = farm["slots"]

    row1 = f'[{get_farm_slot_display(slots["1"])}] [{get_farm_slot_display(slots["2"])}] [{get_farm_slot_display(slots["3"])}]'
    row2 = f'[{get_farm_slot_display(slots["4"])}] [{get_farm_slot_display(slots["5"])}] [{get_farm_slot_display(slots["6"])}]'
    row3 = f'[{get_farm_slot_display(slots["7"])}] [{get_farm_slot_display(slots["8"])}] [{get_farm_slot_display(slots["9"])}]'

    return f"{row1}\n{row2}\n{row3}"

# 檢查哪些格子可種、哪些已佔用
def analyze_plant_targets(guild_id: int, slot_ids: list[int]) -> dict:
    farm = get_or_create_guild_farm(guild_id)

    result = {
        "plantable": [],
        "occupied": [],
        "blocked": [],
        "invalid": [],
    }

    for slot_id in slot_ids:
        slot = farm["slots"].get(str(slot_id))

        if slot is None:
            result["invalid"].append(slot_id)
            continue

        if slot["blocked"]:
            result["blocked"].append(slot_id)
            continue

        if slot.get("crop"):
            result["occupied"].append(slot_id)
            continue

        result["plantable"].append(slot_id)

    return result

# 覆蓋單格資料
def plant_on_slot(slot: dict, seed_key: str, seed_data: dict):
    now = datetime.now(TAIWAN_TZ)
    mature_at = now + timedelta(hours=seed_data["grow_hours"])

    slot["seed_key"] = seed_key
    slot["crop"] = seed_data["name"]
    slot["category"] = seed_data["category"]

    slot["planted_at"] = now.isoformat()
    slot["watered_at"] = None
    slot["fertilized_at"] = None
    slot["mature_at"] = mature_at.isoformat()

    slot["care_hours"] = seed_data["care_hours"]
    slot["notified"] = False
    slot["care_remind_24h_sent"] = False
    slot["care_remind_urgent_sent"] = False


### 種植
def plant_crop(guild_id: int, slot_id: int, seed_key: str) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    slots = farm["slots"]
    slot_key = str(slot_id)

    if slot_key not in slots:
        return False, "找不到這個格子。"

    slot = slots[slot_key]

    if slot["blocked"]:
        return False, "這個位置不能種植。"

    if slot.get("crop"):
        return False, "這個格子已經有作物了。"

    seed_data = SEEDS.get(seed_key)
    if seed_data is None:
        return False, "找不到這種作物。"

    now = datetime.now(TAIWAN_TZ)
    mature_at = now + timedelta(hours=seed_data["grow_hours"])

    slot["seed_key"] = seed_key
    slot["crop"] = seed_data["name"]
    slot["category"] = seed_data["category"]

    slot["planted_at"] = now.isoformat()
    slot["watered_at"] = None
    slot["fertilized_at"] = None
    slot["mature_at"] = mature_at.isoformat()

    slot["care_hours"] = seed_data["care_hours"]
    slot["notified"] = False
    slot["care_remind_24h_sent"] = False
    slot["care_remind_urgent_sent"] = False

    update_guild_farm(guild_id, farm)
    return True, f"已在 {slot_id} 號格種下 {seed_data['name']}。"

# 種植多格植物
def plant_selected_crops(
    guild_id: int,
    slot_ids: list[int],
    seed_key: str,
    overwrite: bool = False
) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    seed_data = SEEDS.get(seed_key)

    if seed_data is None:
        return False, "找不到這種作物。"

    planted = []
    overwritten = []
    skipped = []

    for slot_id in slot_ids:
        slot = farm["slots"].get(str(slot_id))

        if slot is None:
            skipped.append(f"{slot_id}號格（不存在）")
            continue

        if slot["blocked"]:
            skipped.append(f"{slot_id}號格（稻草人）")
            continue

        if slot.get("crop"):
            if not overwrite:
                skipped.append(f"{slot_id}號格（已有 {slot['crop']}）")
                continue

            old_crop = slot["crop"]
            plant_on_slot(slot, seed_key, seed_data)
            overwritten.append(f"{slot_id}號格（{old_crop} → {seed_data['name']}）")
            continue

        plant_on_slot(slot, seed_key, seed_data)
        planted.append(f"{slot_id}號格 {seed_data['name']}")

    if not planted and not overwritten and not skipped:
        return False, "沒有可種植的格子。"

    update_guild_farm(guild_id, farm)

    parts = []
    if planted:
        parts.append("已種植：\n" + "\n".join(planted))
    if overwritten:
        parts.append("已覆蓋：\n" + "\n".join(overwritten))
    if skipped:
        parts.append("未處理：\n" + "\n".join(skipped))

    return True, "\n\n".join(parts)


### 拔除
def uproot_crop(guild_id: int, slot_id: int) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    slots = farm["slots"]
    slot_key = str(slot_id)

    if slot_key not in slots:
        return False, "找不到這個格子。"

    slot = slots[slot_key]

    if slot["blocked"]:
        return False, "這個位置不能操作。"

    if not slot.get("crop"):
        return False, "這個格子目前沒有作物。"

    crop_name = slot["crop"]
    reset_slot(slot)
    update_guild_farm(guild_id, farm)

    return True, f"已拔除 {slot_id} 號格的 {crop_name}。"

# 拔除多格作物
def uproot_selected_crops(guild_id: int, slot_ids: list[int]) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    uprooted = []
    skipped = []

    for slot_id in slot_ids:
        slot = farm["slots"].get(str(slot_id))

        if slot is None:
            skipped.append(f"{slot_id}號格（不存在）")
            continue

        if slot["blocked"]:
            skipped.append(f"{slot_id}號格（稻草人））")
            continue

        if not slot.get("crop"):
            skipped.append(f"{slot_id}號格（空地）")
            continue

        crop_name = slot["crop"]
        reset_slot(slot)
        uprooted.append(f"{slot_id}號格 {crop_name}")

    if not uprooted and not skipped:
        return False, "目前沒有可拔除的作物。"

    update_guild_farm(guild_id, farm)

    parts = []
    if uprooted:
        parts.append("已拔除：\n" + "\n".join(uprooted))
    if skipped:
        parts.append("未處理：\n" + "\n".join(skipped))

    return True, "\n\n".join(parts)


### 收成
def harvest_crop(guild_id: int, slot_id: int, force: bool = False) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    slots = farm["slots"]
    slot_key = str(slot_id)

    if slot_key not in slots:
        return False, "找不到這個格子。"

    slot = slots[slot_key]

    if slot["blocked"]:
        return False, "這個位置不能操作。"

    if not slot.get("crop"):
        return False, "這個格子目前沒有作物。"

    status = get_slot_status(slot)

    if status == "withered":
        return False, "這株作物已經枯萎，不能收成，只能拔除。"

    if status != "mature" and not force:
        return False, "這株作物還沒成熟。"

    crop_name = slot["crop"]
    reset_slot(slot)
    update_guild_farm(guild_id, farm)

    if status == "mature":
        return True, f"已收成 {slot_id} 號格的 {crop_name}。"
    return True, f"已提前收成 {slot_id} 號格的 {crop_name}。"

# 收成多格作物
def harvest_selected_crops(guild_id: int, slot_ids: list[int], force_unripe: bool = False) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    harvested = []
    early = []
    skipped = []

    for slot_id in slot_ids:
        slot = farm["slots"][str(slot_id)]

        if slot["blocked"]:
            skipped.append(f"{slot_id}號格（不可操作）")
            continue

        if not slot.get("crop"):
            skipped.append(f"{slot_id}號格（空地）")
            continue

        status = get_slot_status(slot)

        if status == "withered":
            skipped.append(f"{slot_id}號格（已枯萎）")
            continue

        crop_name = slot["crop"]

        if status == "mature":
            harvested.append(f"{slot_id}號格 {crop_name}")
            reset_slot(slot)
            continue

        if force_unripe:
            early.append(f"{slot_id}號格 {crop_name}")
            reset_slot(slot)
        else:
            skipped.append(f"{slot_id}號格 {crop_name}（未成熟）")

    if not harvested and not early and not skipped:
        return False, "目前沒有可收成的作物。"

    update_guild_farm(guild_id, farm)

    parts = []
    if harvested:
        parts.append("已收成：\n" + "\n".join(harvested))
    if early:
        parts.append("已提前收成：\n" + "\n".join(early))
    if skipped:
        parts.append("未處理：\n" + "\n".join(skipped))

    return True, "\n\n".join(parts)


### 澆水
def water_crop(guild_id: int, slot_id: int) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    slots = farm["slots"]
    slot_key = str(slot_id)

    if slot_key not in slots:
        return False, "找不到這個格子。"

    slot = slots[slot_key]

    if slot["blocked"]:
        return False, "這個位置不能操作。"

    if not slot.get("crop"):
        return False, "這個格子目前沒有作物。"

    status = get_slot_status(slot)
    if status == "withered":
        return False, "這株作物已經枯萎，不能澆水，只能拔除。"

    now = datetime.now(TAIWAN_TZ)
    slot["watered_at"] = now.isoformat()

    # 澆水後重置提醒旗標
    slot["care_remind_24h_sent"] = False
    slot["care_remind_urgent_sent"] = False

    update_guild_farm(guild_id, farm)
    return True, f"已澆水 {slot_id} 號格的 {slot['crop']}。"

# 澆水多格作物
def water_selected_crops(guild_id: int, slot_ids: list[int]) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    changed = []
    skipped = []

    for slot_id in slot_ids:
        slot = farm["slots"][str(slot_id)]

        if slot["blocked"]:
            skipped.append(f"{slot_id}號格（不可操作）")
            continue

        if not slot.get("crop"):
            skipped.append(f"{slot_id}號格（空地）")
            continue

        status = get_slot_status(slot)
        if status == "withered":
            skipped.append(f"{slot_id}號格（已枯萎）")
            continue

        now = datetime.now(TAIWAN_TZ)
        slot["watered_at"] = now.isoformat()
        slot["care_remind_24h_sent"] = False
        slot["care_remind_urgent_sent"] = False
        changed.append(f"{slot_id}號格 {slot['crop']}")

    if not changed and not skipped:
        return False, "目前沒有可澆水的作物。"

    update_guild_farm(guild_id, farm)

    parts = []
    if changed:
        parts.append("已澆水：\n" + "\n".join(changed))
    if skipped:
        parts.append("未處理：\n" + "\n".join(skipped))

    return True, "\n\n".join(parts)


### 施肥
def fertilize_crop(guild_id: int, slot_id: int) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    slots = farm["slots"]
    slot_key = str(slot_id)

    if slot_key not in slots:
        return False, "找不到這個格子。"

    slot = slots[slot_key]

    if slot["blocked"]:
        return False, "這個位置不能操作。"

    if not slot.get("crop"):
        return False, "這個格子目前沒有作物。"

    status = get_slot_status(slot)
    if status == "withered":
        return False, "這株作物已經枯萎，不能施肥。"

    if status == "mature":
        return False, "這株作物已經成熟，不需要施肥。"

    now = datetime.now(TAIWAN_TZ)
    mature_at = parse_iso_datetime(slot.get("mature_at"))
    if mature_at is None:
        return False, "這株作物的成熟時間資料異常。"

    remaining = mature_at - now
    remaining_seconds = remaining.total_seconds()

    if remaining_seconds <= 0:
        return False, "這株作物已經成熟，不需要施肥。"

    reduced_seconds = remaining_seconds * 0.01
    new_mature_at = mature_at - timedelta(seconds=reduced_seconds)

    slot["fertilized_at"] = now.isoformat()
    slot["mature_at"] = new_mature_at.isoformat()

    update_guild_farm(guild_id, farm)
    return True, f"已施肥 {slot_id} 號格的 {slot['crop']}，成熟時間減少 1% 剩餘時間。"

# 施肥多格作物
def fertilize_selected_crops(guild_id: int, slot_ids: list[int]) -> tuple[bool, str]:
    farm = get_or_create_guild_farm(guild_id)
    changed = []
    skipped = []

    for slot_id in slot_ids:
        slot = farm["slots"][str(slot_id)]

        if slot["blocked"]:
            skipped.append(f"{slot_id}號格（不可操作）")
            continue

        if not slot.get("crop"):
            skipped.append(f"{slot_id}號格（空地）")
            continue

        status = get_slot_status(slot)

        if status == "withered":
            skipped.append(f"{slot_id}號格（已枯萎）")
            continue

        if status == "mature":
            skipped.append(f"{slot_id}號格（已成熟）")
            continue

        now = datetime.now(TAIWAN_TZ)
        mature_at = parse_iso_datetime(slot.get("mature_at"))
        if mature_at is None:
            skipped.append(f"{slot_id}號格（成熟時間異常）")
            continue

        remaining_seconds = (mature_at - now).total_seconds()
        if remaining_seconds <= 0:
            skipped.append(f"{slot_id}號格（已成熟）")
            continue

        reduced_seconds = remaining_seconds * 0.01
        new_mature_at = mature_at - timedelta(seconds=reduced_seconds)

        slot["fertilized_at"] = now.isoformat()
        slot["mature_at"] = new_mature_at.isoformat()
        changed.append(f"{slot_id}號格 {slot['crop']}")

    if not changed and not skipped:
        return False, "目前沒有可施肥的作物。"

    update_guild_farm(guild_id, farm)

    parts = []
    if changed:
        parts.append("已施肥：\n" + "\n".join(changed))
    if skipped:
        parts.append("未處理：\n" + "\n".join(skipped))

    return True, "\n\n".join(parts)


# 枯萎時間
def get_care_remaining_text(slot: dict) -> str:
    """取得距離枯萎截止前的剩餘時間文字"""
    if slot["blocked"] or not slot.get("crop"):
        return "--"

    status = get_slot_status(slot)
    if status == "withered":
        return "已枯萎"

    deadline = get_wither_deadline(slot)
    if deadline is None:
        return "無需澆水"

    now = datetime.now(TAIWAN_TZ)
    remaining = deadline - now

    if remaining.total_seconds() <= 0:
        return "已枯萎"

    return format_time_remaining(deadline.isoformat())

# 農田 詳細資訊Render
def render_farm_details(farm: dict) -> str:
    """顯示每格農田的詳細資訊"""
    lines = []
    slots = farm["slots"]

    for slot_id in range(1, 10):
        slot = slots[str(slot_id)]

        if slot["blocked"]:
            continue

        status = get_slot_status(slot)

        if status == "empty":
            lines.append(f"{slot_id}號格：空地")
            continue

        if status == "withered":
            lines.append(
                f"{slot_id}號格：☠️ {slot['crop']}｜已枯萎"
            )
            continue

        if status == "mature":
            care_text = get_care_remaining_text(slot)
            lines.append(
                f"{slot_id}號格：✅ {slot['crop']}｜可收成｜澆水剩餘：{care_text}"
            )
            continue

        grow_text = format_time_remaining(slot.get("mature_at"))
        care_text = get_care_remaining_text(slot)

        lines.append(
            f"{slot_id}號格：🌱 {slot['crop']}｜成熟剩餘：{grow_text}｜澆水剩餘：{care_text}"
        )

    return "\n".join(lines)

# 農田 單一格子 詳細資訊Render
def render_farm_slot_detail(farm: dict, slot_id: int) -> tuple[bool, str]:
    """顯示單一格子的詳細資訊"""
    slot_key = str(slot_id)
    slots = farm["slots"]

    if slot_key not in slots:
        return False, "找不到這個格子。"

    slot = slots[slot_key]

    if slot["blocked"]:
        return True, f"{slot_id}號格：稻草人，不可種植。"

    status = get_slot_status(slot)

    if status == "empty":
        return True, f"{slot_id}號格：空地"

    planted_at = slot.get("planted_at") or "--"
    watered_at = slot.get("watered_at") or "未澆水"
    fertilized_at = slot.get("fertilized_at") or "未施肥"
    mature_text = format_time_remaining(slot.get("mature_at"))
    care_text = get_care_remaining_text(slot)

    status_map = {
        "growing": "生長中",
        "mature": "已成熟",
        "withered": "已枯萎"
    }

    lines = [
        f"{slot_id}號格：{slot['crop']}",
        f"狀態：{status_map.get(status, status)}",
        f"成熟剩餘：{mature_text if status == 'growing' else ('可收成' if status == 'mature' else '--')}",
        f"澆水剩餘：{care_text}",
        f"種植時間：{planted_at}",
        f"上次澆水：{watered_at}",
        f"上次施肥：{fertilized_at}",
    ]

    return True, "\n".join(lines)

### 巡檢邏輯
def collect_farm_alerts() -> list[dict]:
    """
    巡檢所有公會農田，回傳待發送提醒。
    會同步更新提醒旗標並存檔。
    """
    data = load_farm_data()
    alerts: list[dict] = []
    now = datetime.now(TAIWAN_TZ)
    changed = False

    for guild_id_str, farm in data.items():
        guild_id = int(guild_id_str)
        slots = farm.get("slots", {})

        for slot_key, slot in slots.items():
            if slot.get("blocked") or not slot.get("crop"):
                continue

            status = get_slot_status(slot)

            # 1. 成熟提醒（只提醒一次）
            if status == "mature" and not slot.get("notified", False):
                alerts.append({
                    "type": "mature",
                    "guild_id": guild_id,
                    "slot_id": int(slot_key),
                    "crop": slot["crop"],
                    "ping": True,
                })
                slot["notified"] = True
                changed = True
                continue

            # 枯萎或空地就不用檢查澆水提醒
            if status in ("empty", "blocked", "withered", "mature"):
                continue

            # 2. 澆水提醒
            wither_deadline = get_wither_deadline(slot)
            if wither_deadline is None:
                continue

            remaining = wither_deadline - now

            # 24 小時提醒（不 ping）
            if (
                remaining <= timedelta(hours=24)
                and remaining > timedelta(hours=3)
                and not slot.get("care_remind_24h_sent", False)
            ):
                alerts.append({
                    "type": "care_24h",
                    "guild_id": guild_id,
                    "slot_id": int(slot_key),
                    "crop": slot["crop"],
                    "ping": False,
                    "remaining_text": format_time_remaining(wither_deadline.isoformat()),
                })
                slot["care_remind_24h_sent"] = True
                changed = True

            # 快枯死提醒（3 小時內，要 ping）
            if (
                remaining <= timedelta(hours=3)
                and remaining.total_seconds() > 0
                and not slot.get("care_remind_urgent_sent", False)
            ):
                alerts.append({
                    "type": "care_urgent",
                    "guild_id": guild_id,
                    "slot_id": int(slot_key),
                    "crop": slot["crop"],
                    "ping": True,
                    "remaining_text": format_time_remaining(wither_deadline.isoformat()),
                })
                slot["care_remind_urgent_sent"] = True
                changed = True

    if changed:
        save_farm_data(data)

    return alerts
