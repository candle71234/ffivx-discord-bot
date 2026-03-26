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

# 潛水艇時間格式設定\
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


async def submarine_reminder_task(channel_id: int, role_id: int, end_time: datetime, author_name: str):
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

    try:
        await channel.send(
            f"<@&{role_id}> 公會潛水艇探索完成提醒！\n"
            f"由 **{author_name}** 設定的潛水艇已到時間，記得回去收菜 / 再派遣。"
        )
    except Exception as e:
        print(f"[submarine] 發送提醒失敗: {e}")




@bot.command()
@commands.has_permissions(administrator=True)
async def synccommands(ctx):
    await bot.tree.sync()
    await ctx.send("指令同步完成")

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
    


@bot.command()
async def submarine(ctx, *, duration: str):
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
        f"提醒時間：**{end_time.strftime('%Y-%m-%d %H:%M:%S')}** (台灣時間)"
    )


@bot.event
async def on_ready():
    print(f"已登入：{bot.user}")

    if not cactpot_task.is_running():
        cactpot_task.start()
    
    if not reset_notice_task.is_running():
        reset_notice_task.start()


bot.run(token)
