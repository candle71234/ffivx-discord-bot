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

bot.run(DISCORD_BOT_TOKEN)
