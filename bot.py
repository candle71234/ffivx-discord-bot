import os
import re
import json

import discord
from discord.ext import commands, tasks
from discord import app_commands

# 抓時間 & 設定時區
from datetime import time, datetime, timedelta

from config import (
    TAIWAN_TZ,
    DISCORD_BOT_TOKEN,
    REMINDER_CHANNEL_ID,
    DAILY_ROUTINE_ROLE_ID,
    WEEKLY_ROUTINE_ROLE_ID,
    SUBMARINE_DATA_FILE,
)

# farm_system
from farm_system import (
    get_or_create_guild_farm,
    render_farm_grid,
    render_farm_details,
    render_farm_slot_detail,

    get_crop_list_text,
    get_crop_list_text_by_category,
    get_crop_lines,
    get_crop_lines_by_category,
    get_category_label,
    get_crop_choices,
    parse_slot_input,
    analyze_plant_targets,
    crop_matches_category,

    plant_crop,
    plant_selected_crops,

    water_crop,
    water_selected_crops,

    fertilize_crop,
    fertilize_selected_crops,

    harvest_crop,
    harvest_selected_crops,

    uproot_crop,
    uproot_selected_crops,

    get_slot_status,
    get_slot_status_by_id,

    get_category_choices,
    get_crop_choices_by_category,

    collect_farm_alerts,
)


intents = discord.Intents.default()
intents.message_content = True

# 指令前綴 "!"
bot = commands.Bot(command_prefix="!", intents=intents)


# 潛水艇格式
submarine_jobs = {}


def serialize_job(job: dict) -> dict:
    """把記憶體中的 job 轉成可存 JSON 的格式"""
    return {
        "author": job["author"],
        "created_at": job["created_at"].isoformat(),
        "end_time": job["end_time"].isoformat(),
        "duration": job["duration"],
        "channel_id": job["channel_id"],
        "role_id": job["role_id"],
        "notified": job.get("notified", False),
    }


def deserialize_job(data: dict) -> dict:
    """把 JSON 中的 job 轉回程式可用格式"""
    return {
        "author": data["author"],
        "created_at": datetime.fromisoformat(data["created_at"]),
        "end_time": datetime.fromisoformat(data["end_time"]),
        "duration": data["duration"],
        "channel_id": data["channel_id"],
        "role_id": data["role_id"],
        "notified": data.get("notified", False),
    }


def save_submarine_jobs():
    """把目前所有潛水艇提醒存到 JSON"""
    data = {}
    for job_id, job in submarine_jobs.items():
        data[job_id] = serialize_job(job)

    with open(SUBMARINE_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_submarine_jobs():
    """從 JSON 載入潛水艇提醒"""
    global submarine_jobs

    if not os.path.exists(SUBMARINE_DATA_FILE):
        submarine_jobs = {}
        return

    try:
        with open(SUBMARINE_DATA_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        submarine_jobs = {
            job_id: deserialize_job(job_data)
            for job_id, job_data in raw_data.items()
        }
    except Exception as e:
        print(f"[submarine] 載入提醒資料失敗: {e}")
        submarine_jobs = {}


# 潛水艇時間格式設定
def parse_duration(duration_str: str) -> timedelta:
    """
    支援格式：
    1d3h12min
    2h
    45min
    1d
    1d 3h 12min
    """
    text = duration_str.lower().replace(" ", "")

    pattern = r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)min)?$"
    match = re.fullmatch(pattern, text)

    if not match:
        raise ValueError("時間格式錯誤，請使用像 1d3h12min、2h、45min 這種格式")

    days = int(match.group(1)) if match.group(1) else 0
    hours = int(match.group(2)) if match.group(2) else 0
    minutes = int(match.group(3)) if match.group(3) else 0

    if days == 0 and hours == 0 and minutes == 0:
        raise ValueError("時間長度不能是 0")

    return timedelta(days=days, hours=hours, minutes=minutes)

# 潛水艇提醒設定
async def send_submarine_reminder(job_id: str, job: dict):
    """發送單筆潛水艇提醒"""
    channel_id = job["channel_id"]
    role_id = job["role_id"]
    author_name = job["author"]

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            print(f"[submarine] 取得頻道失敗: {e}")
            return False

    try:
        await channel.send(
            f"<@&{role_id}> 公會潛水艇探索完成提醒！\n"
            f"由 **{author_name}** 設定的潛水艇已到時間，記得回去收菜 / 再派遣。"
        )
        return True
    except Exception as e:
        print(f"[submarine] 發送提醒失敗: {e}")
        return False


# 同步指令 目前不會用到
@bot.command()
@commands.has_permissions(administrator=True)
async def synccommands(ctx):
    await bot.tree.sync()
    await ctx.send("指令同步完成")

# !ping
@bot.command()
async def ping(ctx):
    """測試機器人是否在線"""
    await ctx.send("pong")


# 仙人仙彩提醒：每週六 20:30
@tasks.loop(time=time(hour=20, minute=30, tzinfo=TAIWAN_TZ))
async def cactpot_task():
    now = datetime.now(TAIWAN_TZ)

    if now.weekday() == 5:  # 星期六
        print("仙人仙彩提醒觸發")
        channel = bot.get_channel(REMINDER_CHANNEL_ID)
        if channel:
            await channel.send(f"<@&{WEEKLY_ROUTINE_ROLE_ID}> 仙人彩在30分鐘後截止！記得去購買~金鯰魚保佑你🪙")


# 天書奇談 / 老主顧提醒：每週二 15:00
@tasks.loop(time=time(hour=15, minute=00, tzinfo=TAIWAN_TZ))
async def reset_notice_task():
    now = datetime.now(TAIWAN_TZ)

    if now.weekday() == 1:  # 星期二
        print("天書奇談 / 老主顧提醒觸發")
        channel = bot.get_channel(REMINDER_CHANNEL_ID)
        if channel:
            await channel.send(f"<@&{WEEKLY_ROUTINE_ROLE_ID}> 天書奇談跟老主顧將在一個小時候刷新！")

# 仙人仙彩提醒 排程
@cactpot_task.before_loop
async def before_cactpot():
    await bot.wait_until_ready()

# 天書奇談 / 老主顧提醒 排程
@reset_notice_task.before_loop
async def before_reset_notice():
    await bot.wait_until_ready()

# 文字分割器
def split_text_into_chunks(text: str, limit: int = 3800) -> list[str]:
    """
    把長文字切成多段，避免超過 Discord 訊息長度限制
    會盡量以換行為單位切開
    """
    lines = text.splitlines()
    chunks = []
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            if current:
                current += "\n" + line
            else:
                current = line

    if current:
        chunks.append(current)

    return chunks

# 每分鐘檢查潛水艇任務時間  
@tasks.loop(minutes=1)
async def submarine_check_task():
    now = datetime.now(TAIWAN_TZ)
    to_remove = []

    for job_id, job in list(submarine_jobs.items()):
        end_time = job["end_time"]
        notified = job.get("notified", False)

        if notified:
            continue

        if now >= end_time:
            success = await send_submarine_reminder(job_id, job)

            if success:
                print(f"[submarine] 提醒已發送: {job_id} / {job['author']}")
                job["notified"] = True
                to_remove.append(job_id)

    changed = False

    for job_id in to_remove:
        submarine_jobs.pop(job_id, None)
        changed = True

    if changed:
        save_submarine_jobs()


@submarine_check_task.before_loop
async def before_submarine_check():
    await bot.wait_until_ready()


# 預約潛水艇提醒 !sub !submarine
@bot.command(aliases=["sub", "submaine"])
async def submarine(ctx, *, duration: str = None):
    if not duration:
        await ctx.send(
            "🚢 公會潛水艇提醒指令\n\n"
            "用法：`!sub 時間`\n"
            "例如：\n"
            "`!sub 1d3h12min`\n"
            "`!sub 2h`\n"
            "`!sub 45min`\n\n"
            "⏰ 時間單位：\n"
            "- d = 天\n"
            "- h = 小時\n"
            "- min = 分鐘"
        )
        return
    """
    用法:
    !submarine 1d3h12min
    !submarine 2h
    !submarine 45min
    """
    try:
        delta = parse_duration(duration)
    except ValueError as e:
        await ctx.send(
            f"❌ {e}\n"
            f"正確格式：`!submarine 1d3h12min`、`!submarine 2h`、`!submarine 45min`"
        )
        return

    now = datetime.now(TAIWAN_TZ)
    end_time = now + delta

    # 建立唯一 job id
    job_id = f"{ctx.guild.id}-{ctx.channel.id}-{ctx.author.id}-{int(now.timestamp())}"

    submarine_jobs[job_id] = {
        "author": ctx.author.display_name,
        "created_at": now,
        "end_time": end_time,
        "duration": duration,
        "channel_id": REMINDER_CHANNEL_ID,
        "role_id": DAILY_ROUTINE_ROLE_ID,
        "notified": False,
    }
    save_submarine_jobs()

    await ctx.send(
        f"✅ 已設定潛水艇提醒\n"
        f"設定者：**{ctx.author.display_name}**\n"
        f"持續時間：`{duration}`\n"
        f"提醒時間：**{end_time.strftime('%Y-%m-%d %H:%M:%S')}** (台灣時間)\n"
        f"Job ID：`{job_id}`"
    )


# 潛水艇列表查詢 !sublist
@bot.command()
async def sublist(ctx):
    if not submarine_jobs:
        await ctx.send("目前沒有任何潛水艇提醒。")
        return

    now = datetime.now(TAIWAN_TZ)
    lines = []

    for index, (job_id, job) in enumerate(submarine_jobs.items(), start=1):
        remaining = job["end_time"] - now
        total_seconds = int(remaining.total_seconds())

        if total_seconds < 0:
            remaining_text = "即將觸發"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60

            parts = []
            if days > 0:
                parts.append(f"{days}天")
            if hours > 0:
                parts.append(f"{hours}小時")
            if minutes > 0:
                parts.append(f"{minutes}分鐘")

            if not parts:
                parts.append("1分鐘內")

            remaining_text = "".join(parts)

        lines.append(
            f"{index}. 設定者：{job['author']}\n"
            f"   時長：{job['duration']}\n"
            f"   到期時間：{job['end_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"   剩餘時間：{remaining_text}\n"
            f"   Job ID：`{job_id}`"
        )

    await ctx.send("目前潛水艇提醒如下：\n\n" + "\n\n".join(lines))

# 潛水艇取消 !subcancel + id
@bot.command()
async def subcancel(ctx, job_id: str):
    job = submarine_jobs.get(job_id)

    if job is None:
        await ctx.send("❌ 找不到這個提醒 Job ID。請先用 `!sublist` 查看。")
        return

    submarine_jobs.pop(job_id, None)
    save_submarine_jobs()

    await ctx.send(
        f"✅ 已取消潛水艇提醒\n"
        f"設定者：**{job['author']}**\n"
        f"原定提醒時間：**{job['end_time'].strftime('%Y-%m-%d %H:%M:%S')}**"
    )

# !farm
@bot.command()
async def farm(ctx):
    if ctx.guild is None:
        await ctx.send("❌ 農田系統只能在伺服器內使用。")
        return

    farm_data = get_or_create_guild_farm(ctx.guild.id)
    farm_text = render_farm_grid(farm_data)
    farm_details = render_farm_details(farm_data)

    await ctx.send(
        f"🌱 {ctx.guild.name} 的公會農田\n\n"
        f"{farm_text}\n\n"
        f"📋 詳細狀態：\n{farm_details}"
    )

# !farmslot
@bot.command()
async def farmslot(ctx, slot_id: int):
    if ctx.guild is None:
        await ctx.send("❌ 農田系統只能在伺服器內使用。")
        return

    farm_data = get_or_create_guild_farm(ctx.guild.id)
    ok, message = render_farm_slot_detail(farm_data, slot_id)
    await ctx.send(message)

# !farmhelp
@bot.command()
async def farmhelp(ctx):
    help_text = (
        "🌱 **公會農田指令說明**\n\n"

        "📋 **查看農田**\n"
        "`/farm`：查看整塊公會農田，方向以面對稻草人為上\\n"
        "`/farmslot <格子>`：查看單一格詳細資訊\n"
        "`/crops`：查看可種植作物列表\n\n"

        "🌾 **種植**\n"
        "`/plant <格子> <作物key>`：在指定格子種植\n"
        "`/plant <多格> <作物key>`：一次種多格\n"
        "`/plant all <作物key>`：整片田種植\n\n"

        "格子可輸入格式：\n"
        "`1`：單格\n"
        "`1246`：多格\n"
        "`1,2,4,6`：多格\n"
        "`all`：全部可用格子\n\n"

        "如果選到已有作物的格子：\n"
        "`e` = 只種空地\n"
        "`o` = 全部覆蓋\n"
        "`n` = 取消\n\n"

        "💧 **澆水**\n"
        "`/water <格子>`：澆單格\n"
        "`/water <多格>`：澆多格\n"
        "`/water all`：全部澆水\n\n"

        "🧪 **施肥**\n"
        "`/fertilize <格子>`：單格施肥\n"
        "`/fertilize <多格>`：多格施肥\n"
        "`/fertilize all`：全部施肥\n"
        "效果：每次施肥會減少該作物 **1% 剩餘成熟時間**\n\n"

        "🌾 **收成**\n"
        "`/harvest <格子>`：收單格\n"
        "`/harvest <多格>`：收多格\n"
        "`/harvest all`：全部收成\n\n"

        "收成規則：\n"
        "- 已成熟：直接收成\n"
        "- 未成熟：會詢問是否提前收成\n"
        "- 多格時如果有未成熟作物：\n"
        "  `m` = 只收成熟的\n"
        "  `a` = 全部收成\n"
        "  `n` = 取消\n\n"

        "🪓 **拔除**\n"
        "`/uproot <格子>`：拔單格\n"
        "`/uproot <多格>`：拔多格\n"
        "`/uproot all`：全部拔除\n\n"

        "⏰ **提醒規則**\n"
        "- 作物成熟時會提醒\n"
        "- 距離枯萎剩 24 小時會提醒一次（不 ping）\n"
        "- 距離枯萎很近時會提醒一次（會 ping）\n"
        "- 超過照顧時間沒澆水，作物會枯萎\n\n"

        "💡 **建議**\n"
        "平常優先使用 slash 指令：\n"
        "`/farm` `/farmslot` `/plant` `/water` `/fertilize` `/harvest` `/uproot`\n"
        "slash 指令支援自動補完，而且多數可以只讓自己看到。"
    )

    await ctx.send(help_text)


# !crops  
@bot.command()
async def crops(ctx, category: str = None):
    if category is None:
        title = "全部作物"
        lines = get_crop_lines()
    else:
        category_key = category.lower()
        title = f"{get_category_label(category_key)} 作物"
        lines = get_crop_lines(category_key)

    view = CropsPaginationView(title=title, lines=lines, per_page=8)
    view.update_buttons()

    await ctx.send(embed=view.build_embed(), view=view)
    
# !plant  
@bot.command()
async def plant(ctx, target: str, crop_key: str):
    if ctx.guild is None:
        await ctx.send("❌ 農田系統只能在伺服器內使用。")
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await ctx.send(parsed)
        return

    analysis = analyze_plant_targets(ctx.guild.id, parsed)

    if not analysis["plantable"] and not analysis["occupied"]:
        parts = []
        if analysis["blocked"]:
            parts.append("不可種植：\n" + "\n".join(f"{x}號格（稻草人）" for x in analysis["blocked"]))
        if analysis["invalid"]:
            parts.append("無效格子：\n" + "\n".join(f"{x}號格" for x in analysis["invalid"]))

        message = "\n\n".join(parts) if parts else "沒有可種植的格子。"
        await ctx.send(message)
        return

    if analysis["occupied"]:
        parts = [f"🌱 準備種植：`{crop_key}`"]

        if analysis["plantable"]:
            parts.append("空地：\n" + "\n".join(f"{x}號格" for x in analysis["plantable"]))
        if analysis["occupied"]:
            parts.append("已有作物：\n" + "\n".join(f"{x}號格" for x in analysis["occupied"]))

        await ctx.send(
            "\n\n".join(parts) +
            "\n\n請選擇：\n"
            "`e` = 只種空地\n"
            "`o` = 全部覆蓋\n"
            "`n` = 取消\n\n"
            "請在 20 秒內回覆。"
        )

        def check(m: discord.Message):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.lower() in ("e", "o", "n")
            )

        try:
            reply = await bot.wait_for("message", timeout=20, check=check)
        except Exception:
            await ctx.send("⌛ 已超時，取消種植。")
            return

        choice = reply.content.lower()

        if choice == "n":
            await ctx.send("已取消種植。")
            return

        overwrite = choice == "o"
        success, message = plant_selected_crops(
            ctx.guild.id,
            parsed,
            crop_key.lower(),
            overwrite=overwrite
        )
        await ctx.send(message)
        return

    success, message = plant_selected_crops(
        ctx.guild.id,
        parsed,
        crop_key.lower(),
        overwrite=False
    )
    await ctx.send(message)

# !uproot 拔菜
@bot.command()
async def uproot(ctx, target: str):
    if ctx.guild is None:
        await ctx.send("❌ 農田系統只能在伺服器內使用。")
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await ctx.send(parsed)
        return

    # 分析目前狀態
    farm_data = get_or_create_guild_farm(ctx.guild.id)

    valid_slots = []
    for slot_id in parsed:
        slot = farm_data["slots"].get(str(slot_id))

        if slot is None or slot["blocked"]:
            continue

        if slot.get("crop"):
            valid_slots.append((slot_id, slot["crop"]))

    if not valid_slots:
        await ctx.send("沒有可拔除的作物。")
        return

    # 顯示確認內容
    preview = "\n".join([f"{sid}號格：{crop}" for sid, crop in valid_slots])

    await ctx.send(
        f"⚠️ 確定要拔除以下作物嗎？\n\n{preview}\n\n"
        "輸入 `y` 確認，`n` 取消（20秒內）"
    )

    def check(m: discord.Message):
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.lower() in ("y", "n")
        )

    try:
        reply = await bot.wait_for("message", timeout=20, check=check)
    except Exception:
        await ctx.send("⌛ 已超時，取消拔除。")
        return

    if reply.content.lower() == "n":
        await ctx.send("已取消拔除。")
        return

    success, message = uproot_selected_crops(ctx.guild.id, parsed)
    await ctx.send(message)

# !harvest 收成
@bot.command()
async def harvest(ctx, target: str):
    if ctx.guild is None:
        await ctx.send("❌ 農田系統只能在伺服器內使用。")
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await ctx.send(parsed)
        return

    # 多格 / all
    if len(parsed) > 1:
        farm_data = get_or_create_guild_farm(ctx.guild.id)

        has_unripe = False
        for slot_id in parsed:
            slot = farm_data["slots"][str(slot_id)]
            if slot["blocked"] or not slot.get("crop"):
                continue

            status = get_slot_status(slot)
            if status == "growing":
                has_unripe = True
                break

        if not has_unripe:
            success, message = harvest_selected_crops(ctx.guild.id, parsed, force_unripe=False)
            await ctx.send(message)
            return

        await ctx.send(
            "⚠️ 你選擇的格子中有尚未成熟的作物，請選擇操作：\n"
            "`m` = 只收成熟的\n"
            "`a` = 全部收成（包含未成熟）\n"
            "`n` = 取消\n\n"
            "請在 20 秒內回覆。"
        )

        def check(m: discord.Message):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.lower() in ("m", "a", "n")
            )

        try:
            reply = await bot.wait_for("message", timeout=20, check=check)
        except Exception:
            await ctx.send("⌛ 已超時，取消收成。")
            return

        choice = reply.content.lower()

        if choice == "n":
            await ctx.send("已取消收成。")
            return

        if choice == "m":
            success, message = harvest_selected_crops(ctx.guild.id, parsed, force_unripe=False)
            await ctx.send(message)
            return

        if choice == "a":
            success, message = harvest_selected_crops(ctx.guild.id, parsed, force_unripe=True)
            await ctx.send(message)
            return

    # 單格
    slot_id = parsed[0]
    ok, status_or_msg, slot = get_slot_status_by_id(ctx.guild.id, slot_id)

    if not ok:
        await ctx.send(status_or_msg)
        return

    if status_or_msg == "withered":
        await ctx.send("這株作物已經枯萎，不能收成，只能拔除。")
        return

    if status_or_msg == "mature":
        success, message = harvest_crop(ctx.guild.id, slot_id, force=False)
        await ctx.send(message)
        return

    await ctx.send(
        f"⚠️ {slot_id} 號格的 **{slot['crop']}** 還沒成熟，確定要提前收成嗎？(y/n)\n"
        "請在 20 秒內回覆。"
    )

    def check(m: discord.Message):
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.lower() in ("y", "n", "yes", "no")
        )

    try:
        reply = await bot.wait_for("message", timeout=20, check=check)
    except Exception:
        await ctx.send("⌛ 已超時，取消提前收成。")
        return

    if reply.content.lower() in ("n", "no"):
        await ctx.send("已取消收成。")
        return

    success, message = harvest_crop(ctx.guild.id, slot_id, force=True)
    await ctx.send(message)


# !water 澆水
@bot.command()
async def water(ctx, target: str):
    if ctx.guild is None:
        await ctx.send("❌ 農田系統只能在伺服器內使用。")
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await ctx.send(parsed)
        return

    success, message = water_selected_crops(ctx.guild.id, parsed)
    await ctx.send(message)


# !fertilize 施肥
@bot.command()
async def fertilize(ctx, target: str):
    if ctx.guild is None:
        await ctx.send("❌ 農田系統只能在伺服器內使用。")
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await ctx.send(parsed)
        return

    success, message = fertilize_selected_crops(ctx.guild.id, parsed)
    await ctx.send(message)




# /farmhelp
@bot.tree.command(name="farmhelp", description="查看公會農田系統說明")
async def farmhelp_slash(interaction: discord.Interaction):
    help_text = (
        "🌱 **公會農田指令說明**\n\n"

        "📋 **查看農田**\n"
        "`/farm`：查看整塊公會農田，方向以面對稻草人為上\n"
        "`/farmslot <格子>`：查看單一格詳細資訊\n"
        "`/crops`：查看可種植作物列表\n\n"

        "🌾 **種植**\n"
        "`/plant <格子> <作物key>`：在指定格子種植\n"
        "`/plant <多格> <作物key>`：一次種多格\n"
        "`/plant all <作物key>`：整片田種植\n\n"

        "格子可輸入格式：\n"
        "`1`、`1246`、`1,2,4,6`、`all`\n\n"

        "如果選到已有作物的格子：\n"
        "`e` = 只種空地\n"
        "`o` = 全部覆蓋\n"
        "`n` = 取消\n\n"

        "💧 **澆水**\n"
        "`/water <格子>` / `/water <多格>` / `/water all`\n\n"

        "🧪 **施肥**\n"
        "`/fertilize <格子>` / `/fertilize <多格>` / `/fertilize all`\n"
        "效果：每次施肥減少 **1% 剩餘成熟時間**\n\n"

        "🌾 **收成**\n"
        "`/harvest <格子>` / `/harvest <多格>` / `/harvest all`\n"
        "多格含未成熟時：\n"
        "`m` = 只收成熟的 / `a` = 全收 / `n` = 取消\n\n"

        "🪓 **拔除**\n"
        "`/uproot <格子>` / `/uproot <多格>` / `/uproot all`\n\n"

        "⏰ **提醒**\n"
        "- 成熟提醒\n"
        "- 24 小時枯萎提醒（不 ping）\n"
        "- 緊急枯萎提醒（會 ping）"
    )

    await interaction.response.send_message(help_text, ephemeral=True)


### 農田巡查 ###
@tasks.loop(minutes=1)
async def farm_check_task():
    alerts = collect_farm_alerts()

    if not alerts:
        return

    channel = bot.get_channel(REMINDER_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(REMINDER_CHANNEL_ID)
        except Exception as e:
            print(f"[farm] 取得提醒頻道失敗: {e}")
            return

    for alert in alerts:
        try:
            if alert["type"] == "mature":
                prefix = f"<@&{DAILY_ROUTINE_ROLE_ID}> " if alert["ping"] else ""
                await channel.send(
                    f"{prefix}🌾 農田提醒：{alert['slot_id']} 號格的 **{alert['crop']}** 已成熟，可以收成了！"
                )

            elif alert["type"] == "care_24h":
                await channel.send(
                    f"💧 農田提醒：{alert['slot_id']} 號格的 **{alert['crop']}** 需要在 "
                    f"**{alert['remaining_text']}** 內澆水，否則會枯萎。"
                )

            elif alert["type"] == "care_urgent":
                prefix = f"<@&{DAILY_ROUTINE_ROLE_ID}> " if alert["ping"] else ""
                await channel.send(
                    f"{prefix}⚠️ 農田緊急提醒：{alert['slot_id']} 號格的 **{alert['crop']}** "
                    f"再 **{alert['remaining_text']}** 就會枯萎，請盡快澆水！"
                )

        except Exception as e:
            print(f"[farm] 發送提醒失敗: {e}")



@farm_check_task.before_loop
async def before_farm_check():
    await bot.wait_until_ready()

async def farm_slot_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    slot_choices = ["1", "2", "3", "4", "6", "7", "8", "9"]

    return [
        app_commands.Choice(name=f"{slot}號格", value=slot)
        for slot in slot_choices
        if current in slot
    ][:25]

# 農田作物分類自動拼寫
async def crop_category_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    current = current.lower()

    return [
        app_commands.Choice(name=label, value=key)
        for label, key in get_category_choices()
        if current in key.lower() or current in label.lower()
    ][:25]

# 農田作物自動拼寫
async def crop_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    current = current.lower().strip()
    category = getattr(interaction.namespace, "category", None)

    if category:
        source = get_crop_choices_by_category(category)
    else:
        source = get_crop_choices()

    return [
        app_commands.Choice(name=label, value=crop_key)
        for label, crop_key in source
        if current in crop_key.lower() or current in label.lower()
    ][:25]

# 農田格子自動拼寫
async def farm_target_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    presets = [
        ("全部格子", "all"),
        ("四個角落格子(1、3、7、9)", "1379"),
        ("十字格子", "2、4、6、8"),
        ("1號格(左上)", "1"),
        ("2號格(中上)", "2"),
        ("3號格(右上)", "3"),
        ("4號格(左中)", "4"),
        ("6號格(右中)", "6"),
        ("7號格(左下)", "7"),
        ("8號格(中下)", "8"),
        ("9號格(右下)", "9"),
    ]

    current = current.lower().strip()

    return [
        app_commands.Choice(name=label, value=value)
        for label, value in presets
        if current in value.lower() or current in label.lower()
    ][:25]

# 潛艦ID自動拼寫
async def submarine_job_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    choices = []

    for job_id, job in submarine_jobs.items():
        label = f"{job['author']} | {job['end_time'].strftime('%m-%d %H:%M')}"

        # 搜尋過濾（打字篩選）
        if current.lower() in label.lower() or current.lower() in job_id.lower():
            choices.append(
                app_commands.Choice(
                    name=label[:100],  # Discord 限制長度
                    value=job_id
                )
            )

    return choices[:25]  # Discord 最多 25 個選項


### 建立 /sub 指令集
sub_group = app_commands.Group(name="sub", description="公會潛水艇提醒相關指令")

# /sub add
@sub_group.command(name="add", description="新增潛水艇提醒")
@app_commands.describe(
    days="天數",
    hours="小時",
    minutes="分鐘"
)
async def sub_add(
    interaction: discord.Interaction,
    days: app_commands.Range[int, 0, 30] = 0,
    hours: app_commands.Range[int, 0, 23] = 0,
    minutes: app_commands.Range[int, 0, 59] = 0
):
    if days == 0 and hours == 0 and minutes == 0:
        await interaction.response.send_message(
            "❌ 至少要填一個時間，不能全部都是 0。",
            ephemeral=True
        )
        return

    delta = timedelta(days=days, hours=hours, minutes=minutes)
    now = datetime.now(TAIWAN_TZ)
    end_time = now + delta

    job_id = f"{interaction.guild.id}-{interaction.channel.id}-{interaction.user.id}-{int(now.timestamp())}"

    submarine_jobs[job_id] = {
        "author": interaction.user.display_name,
        "created_at": now,
        "end_time": end_time,
        "duration": f"{days}d {hours}h {minutes}min",
        "channel_id": REMINDER_CHANNEL_ID,
        "role_id": DAILY_ROUTINE_ROLE_ID,
        "notified": False,
    }
    save_submarine_jobs()

    
    await interaction.response.send_message(
        f"✅ 已設定潛水艇提醒\n"
        f"設定者：**{interaction.user.display_name}**\n"
        f"持續時間：`{days}天 {hours}小時 {minutes}分鐘`\n"
        f"提醒時間：**{end_time.strftime('%Y-%m-%d %H:%M:%S')}** (台灣時間)\n"
        f"Job ID：`{job_id}`"
    )

# /sub list
@sub_group.command(name="list", description="查看目前所有潛水艇提醒")
async def sub_list(interaction: discord.Interaction):
    if not submarine_jobs:
        await interaction.response.send_message("目前沒有任何潛水艇提醒。", ephemeral=True)
        return

    now = datetime.now(TAIWAN_TZ)
    lines = []

    for index, (job_id, job) in enumerate(submarine_jobs.items(), start=1):
        remaining = job["end_time"] - now
        total_seconds = int(remaining.total_seconds())

        if total_seconds < 0:
            remaining_text = "即將觸發"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60

            parts = []
            if days > 0:
                parts.append(f"{days}天")
            if hours > 0:
                parts.append(f"{hours}小時")
            if minutes > 0:
                parts.append(f"{minutes}分鐘")
            if not parts:
                parts.append("1分鐘內")

            remaining_text = "".join(parts)

        lines.append(
            f"{index}. 設定者：{job['author']}\n"
            f"   時長：{job['duration']}\n"
            f"   到期時間：{job['end_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"   剩餘時間：{remaining_text}\n"
            f"   Job ID：`{job_id}`"
        )

    message = "目前潛水艇提醒如下：\n\n" + "\n\n".join(lines)
    await interaction.response.send_message(message, ephemeral=True)

# /sub cancel
@sub_group.command(name="cancel", description="取消指定的潛水艇提醒")
@app_commands.describe(job_id="選擇要取消的提醒")
@app_commands.autocomplete(job_id=submarine_job_autocomplete)
async def sub_cancel(interaction: discord.Interaction, job_id: str):
    job = submarine_jobs.get(job_id)

    if job is None:
        await interaction.response.send_message(
            "❌ 找不到這個提醒 Job ID。請先用 `/sub list` 查看。",
            ephemeral=True
        )
        return

    submarine_jobs.pop(job_id, None)
    save_submarine_jobs()

    await interaction.response.send_message(
        f"✅ 已取消潛水艇提醒\n"
        f"設定者：**{job['author']}**\n"
        f"原定提醒時間：**{job['end_time'].strftime('%Y-%m-%d %H:%M:%S')}**",
        ephemeral=True
    )

bot.tree.add_command(sub_group)

### 農田SLASH指令
@bot.tree.command(name="farm", description="查看公會農田")
async def farm_slash(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("❌ 農田系統只能在伺服器內使用。", ephemeral=True)
        return

    farm_data = get_or_create_guild_farm(interaction.guild.id)
    farm_text = render_farm_grid(farm_data)
    farm_details = render_farm_details(farm_data)

    await interaction.response.send_message(
        f"🌱 {interaction.guild.name} 的公會農田\n\n{farm_text}\n\n📋 詳細狀態：\n{farm_details}",
        ephemeral=True
    )

# /farmslot
@bot.tree.command(name="farmslot", description="查看單一格農田資訊")
@app_commands.describe(slot_id="要查看的格子")
@app_commands.autocomplete(slot_id=farm_target_autocomplete)
async def farmslot_slash(interaction: discord.Interaction, slot_id: str):
    if interaction.guild is None:
        await interaction.response.send_message("❌ 農田系統只能在伺服器內使用。", ephemeral=True)
        return

    ok, parsed = parse_slot_input(slot_id)
    if not ok or len(parsed) != 1:
        await interaction.response.send_message("請只指定一個格子。", ephemeral=True)
        return

    farm_data = get_or_create_guild_farm(interaction.guild.id)
    ok, message = render_farm_slot_detail(farm_data, parsed[0])
    await interaction.response.send_message(message, ephemeral=True)

# Plant View
class PlantChoiceView(discord.ui.View):
    def __init__(self, guild_id: int, slot_ids: list[int], crop_key: str):
        super().__init__(timeout=30)
        self.guild_id = guild_id
        self.slot_ids = slot_ids
        self.crop_key = crop_key

    @discord.ui.button(label="只種空地", style=discord.ButtonStyle.success)
    async def plant_empty_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, message = plant_selected_crops(
            self.guild_id,
            self.slot_ids,
            self.crop_key,
            overwrite=False
        )
        await interaction.response.edit_message(content=message, view=None)

    @discord.ui.button(label="全部覆蓋", style=discord.ButtonStyle.danger)
    async def overwrite_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, message = plant_selected_crops(
            self.guild_id,
            self.slot_ids,
            self.crop_key,
            overwrite=True
        )
        await interaction.response.edit_message(content=message, view=None)

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="已取消種植。", view=None)

# /plant
@bot.tree.command(name="plant", description="在指定格子種植作物")
@app_commands.describe(
    target="例如 1、1246、1,2,4,6 或 all",
    category="可選，先指定作物分類",
    crop_key="選擇要種的作物"
)
@app_commands.autocomplete(
    target=farm_target_autocomplete,
    category=crop_category_autocomplete,
    crop_key=crop_autocomplete
)
async def plant_slash(
    interaction: discord.Interaction,
    target: str,
    crop_key: str,
    category: str | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ 農田系統只能在伺服器內使用。",
            ephemeral=True
        )
        return

    if not crop_matches_category(crop_key.lower(), category.lower() if category else None):
        await interaction.response.send_message(
            "❌ 你選的作物不屬於這個分類，請重新選擇。",
            ephemeral=True
        )
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await interaction.response.send_message(parsed, ephemeral=True)
        return

    analysis = analyze_plant_targets(interaction.guild.id, parsed)

    if not analysis["plantable"] and not analysis["occupied"]:
        parts = []
        if analysis["blocked"]:
            parts.append("不可種植：\n" + "\n".join(f"{x}號格（稻草人）" for x in analysis["blocked"]))
        if analysis["invalid"]:
            parts.append("無效格子：\n" + "\n".join(f"{x}號格" for x in analysis["invalid"]))

        await interaction.response.send_message(
            "\n\n".join(parts) if parts else "沒有可種植的格子。",
            ephemeral=True
        )
        return

    if analysis["occupied"]:
        parts = [f"🌱 準備種植：`{crop_key}`"]

        if analysis["plantable"]:
            parts.append("空地：\n" + "\n".join(f"{x}號格" for x in analysis["plantable"]))
        if analysis["occupied"]:
            parts.append("已有作物：\n" + "\n".join(f"{x}號格" for x in analysis["occupied"]))

        view = PlantChoiceView(interaction.guild.id, parsed, crop_key.lower())
        await interaction.response.send_message(
            "\n\n".join(parts) + "\n\n請選擇要如何處理已有作物的格子：",
            view=view,
            ephemeral=True
        )
        return

    success, message = plant_selected_crops(
        interaction.guild.id,
        parsed,
        crop_key.lower(),
        overwrite=False
    )
    await interaction.response.send_message(message, ephemeral=True)
    

# /water
@bot.tree.command(name="water", description="澆水，可指定單格、多格或 all")
@app_commands.describe(target="例如 1、1246、1,2,4,6 或 all")
@app_commands.autocomplete(target=farm_target_autocomplete)
async def water_slash(interaction: discord.Interaction, target: str):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ 農田系統只能在伺服器內使用。",
            ephemeral=True
        )
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await interaction.response.send_message(parsed, ephemeral=True)
        return

    success, message = water_selected_crops(interaction.guild.id, parsed)
    await interaction.response.send_message(message, ephemeral=True)

# /fertilize
@bot.tree.command(name="fertilize", description="施肥，可指定單格、多格或 all")
@app_commands.describe(target="例如 1、1246、1,2,4,6 或 all")
@app_commands.autocomplete(target=farm_target_autocomplete)
async def fertilize_slash(interaction: discord.Interaction, target: str):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ 農田系統只能在伺服器內使用。",
            ephemeral=True
        )
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await interaction.response.send_message(parsed, ephemeral=True)
        return

    success, message = fertilize_selected_crops(interaction.guild.id, parsed)
    await interaction.response.send_message(message, ephemeral=True)

# /uproot 按鈕
class UprootConfirmView(discord.ui.View):
    def __init__(self, guild_id: int, slot_ids: list[int]):
        super().__init__(timeout=30)
        self.guild_id = guild_id
        self.slot_ids = slot_ids

    @discord.ui.button(label="確認拔除", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, message = uproot_selected_crops(self.guild_id, self.slot_ids)
        await interaction.response.edit_message(content=message, view=None)

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="已取消拔除。", view=None)

# /uproot
@bot.tree.command(name="uproot", description="拔除作物，可指定單格、多格或 all")
@app_commands.describe(target="例如 1、1246、1,2,4,6 或 all")
@app_commands.autocomplete(target=farm_target_autocomplete)
async def uproot_slash(interaction: discord.Interaction, target: str):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ 農田系統只能在伺服器內使用。",
            ephemeral=True
        )
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await interaction.response.send_message(parsed, ephemeral=True)
        return

    farm_data = get_or_create_guild_farm(interaction.guild.id)

    valid_slots = []
    for slot_id in parsed:
        slot = farm_data["slots"].get(str(slot_id))

        if slot is None or slot["blocked"]:
            continue

        if slot.get("crop"):
            valid_slots.append((slot_id, slot["crop"]))

    if not valid_slots:
        await interaction.response.send_message("沒有可拔除的作物。", ephemeral=True)
        return

    preview = "\n".join([f"{sid}號格：{crop}" for sid, crop in valid_slots])

    view = UprootConfirmView(interaction.guild.id, parsed)

    await interaction.response.send_message(
        f"⚠️ 確定要拔除以下作物嗎？\n\n{preview}",
        view=view,
        ephemeral=True
    )

# /harvest 按鈕
class HarvestChoiceView(discord.ui.View):
    def __init__(self, guild_id: int, slot_ids: list[int]):
        super().__init__(timeout=30)
        self.guild_id = guild_id
        self.slot_ids = slot_ids

    @discord.ui.button(label="只收成熟的", style=discord.ButtonStyle.success)
    async def harvest_ripe_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, message = harvest_selected_crops(self.guild_id, self.slot_ids, force_unripe=False)
        await interaction.response.edit_message(content=message, view=None)

    @discord.ui.button(label="全部收成", style=discord.ButtonStyle.danger)
    async def harvest_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, message = harvest_selected_crops(self.guild_id, self.slot_ids, force_unripe=True)
        await interaction.response.edit_message(content=message, view=None)

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="已取消收成。", view=None)

# /harvest
@bot.tree.command(name="harvest", description="收成，可指定單格、多格或 all")
@app_commands.describe(target="例如 1、1246、1,2,4,6 或 all")
@app_commands.autocomplete(target=farm_target_autocomplete)
async def harvest_slash(interaction: discord.Interaction, target: str):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ 農田系統只能在伺服器內使用。",
            ephemeral=True
        )
        return

    ok, parsed = parse_slot_input(target)
    if not ok:
        await interaction.response.send_message(parsed, ephemeral=True)
        return

    farm_data = get_or_create_guild_farm(interaction.guild.id)

    has_unripe = False
    has_mature = False

    for slot_id in parsed:
        slot = farm_data["slots"][str(slot_id)]
        if slot["blocked"] or not slot.get("crop"):
            continue

        status = get_slot_status(slot)
        if status == "growing":
            has_unripe = True
        elif status == "mature":
            has_mature = True

    if not has_unripe:
        success, message = harvest_selected_crops(interaction.guild.id, parsed, force_unripe=False)
        await interaction.response.send_message(message, ephemeral=True)
        return

    view = HarvestChoiceView(interaction.guild.id, parsed)
    await interaction.response.send_message(
        "⚠️ 你選擇的格子中有尚未成熟的作物，請選擇要怎麼收成：",
        view=view,
        ephemeral=True
    )

# Crops View
class CropsPaginationView(discord.ui.View):
    def __init__(self, title: str, lines: list[str], per_page: int = 8):
        super().__init__(timeout=120)
        self.title = title
        self.lines = lines
        self.per_page = per_page
        self.page = 0

    @property
    def total_pages(self) -> int:
        if not self.lines:
            return 1
        return (len(self.lines) - 1) // self.per_page + 1

    def get_page_lines(self) -> list[str]:
        if not self.lines:
            return []

        start = self.page * self.per_page
        end = start + self.per_page
        return self.lines[start:end]

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🌾 {self.title}",
            description="可使用左右按鈕翻頁查看作物列表。",
        )

        page_lines = self.get_page_lines()

        if not page_lines:
            embed.add_field(
                name="沒有資料",
                value="這個分類目前沒有可顯示的作物。",
                inline=False
            )
        else:
            embed.add_field(
                name="作物清單",
                value="\n".join(page_lines),
                inline=False
            )

        embed.set_footer(
            text=f"第 {self.page + 1} / {self.total_pages} 頁｜每頁 {self.per_page} 筆"
        )
        return embed

    def update_buttons(self):
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.total_pages - 1

    @discord.ui.button(label="⬅ 上一頁", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="下一頁 ➡", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="關閉", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="已關閉作物列表。",
            embed=None,
            view=None
        )

# /crops
@bot.tree.command(name="crops", description="查看可種植作物")
@app_commands.describe(category="可選，指定要查看的分類")
@app_commands.autocomplete(category=crop_category_autocomplete)
async def crops_slash(interaction: discord.Interaction, category: str | None = None):
    if category is None:
        title = "全部作物"
        lines = get_crop_lines()
    else:
        category_key = category.lower()
        title = f"{get_category_label(category_key)} 作物"
        lines = get_crop_lines(category_key)

    view = CropsPaginationView(title=title, lines=lines, per_page=8)
    view.update_buttons()

    await interaction.response.send_message(
        embed=view.build_embed(),
        view=view,
        ephemeral=True
    )

### 機器人啟動程序 
@bot.event
async def on_ready():
    print(f"已登入：{bot.user}")

    load_submarine_jobs()
    print(f"[submarine] 已載入 {len(submarine_jobs)} 筆提醒資料")

    if not cactpot_task.is_running():
        cactpot_task.start()
    
    if not reset_notice_task.is_running():
        reset_notice_task.start()

    if not submarine_check_task.is_running():
        submarine_check_task.start()

    if not farm_check_task.is_running():
        farm_check_task.start()
        

bot.run(DISCORD_BOT_TOKEN)
