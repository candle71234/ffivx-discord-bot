import os
import re
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks

# 本地用
from dotenv import load_dotenv
load_dotenv()

# 抓時間 & 設定時區
from datetime import time, datetime, timedelta
from zoneinfo import ZoneInfo
TAIWAN_TZ = ZoneInfo("Asia/Taipei")

# 從環境抓
token = os.getenv("DISCORD_BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))
TARGET_ROLE_ID = int(os.getenv("TARGET_ROLE_ID"))


intents = discord.Intents.default()
intents.message_content = True

# 指令前綴 "!"
bot = commands.Bot(command_prefix="!", intents=intents)



# 用來保存目前排程中的潛水艇提醒
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
async def submarine_reminder_task(job_id: str, channel_id: int, role_id: int, end_time: datetime, author_name: str):
    try:
        now = datetime.now(TAIWAN_TZ)
        wait_seconds = (end_time - now).total_seconds()

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception as e:
                print(f"[submarine] 取得頻道失敗: {e}")
                return

        await channel.send(
            f"<@&{role_id}> 公會潛水艇探索完成提醒！\n"
            f"由 **{author_name}** 設定的潛水艇已到時間，記得回去收菜 / 再派遣。"
        )

    except Exception as e:
        print(f"[submarine] 發送提醒失敗: {e}")

    finally:
        submarine_jobs.pop(job_id, None)
        print(f"[submarine] 已清除提醒 job: {job_id}")


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
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        if channel:
            await channel.send(f"<@&{TARGET_ROLE_ID}> 記得去抽獎！")


# 天書奇談 / 老主顧提醒：每週二 15:00
@tasks.loop(time=time(hour=15, minute=00, tzinfo=TAIWAN_TZ))
async def reset_notice_task():
    now = datetime.now(TAIWAN_TZ)

    if now.weekday() == 1:  # 星期二
        print("天書奇談 / 老主顧提醒觸發")
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        if channel:
            await channel.send(f"<@&{TARGET_ROLE_ID}> 天書奇談跟老主顧再一個小時刷新(測試)")

# 仙人仙彩提醒 排程
@cactpot_task.before_loop
async def before_cactpot():
    await bot.wait_until_ready()

# 天書奇談 / 老主顧提醒 排程
@reset_notice_task.before_loop
async def before_reset_notice():
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

    task = asyncio.create_task(
        submarine_reminder_task(
            job_id=job_id,
            channel_id=TARGET_CHANNEL_ID,
            role_id=TARGET_ROLE_ID,
            end_time=end_time,
            author_name=ctx.author.display_name
        )
    )

    submarine_jobs[job_id] = {
        "task": task,
        "author": ctx.author.display_name,
        "created_at": now,
        "end_time": end_time,
        "duration": duration,
    }

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

    task = job["task"]
    task.cancel()

    submarine_jobs.pop(job_id, None)

    await ctx.send(
        f"✅ 已取消潛水艇提醒\n"
        f"設定者：**{job['author']}**\n"
        f"原定提醒時間：**{job['end_time'].strftime('%Y-%m-%d %H:%M:%S')}**"
    )


@bot.event
async def on_ready():
    print(f"已登入：{bot.user}")

    if not cactpot_task.is_running():
        cactpot_task.start()
    
    if not reset_notice_task.is_running():
        reset_notice_task.start()


bot.run(token)
