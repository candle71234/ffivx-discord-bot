import os

import discord
from discord.ext import commands
from discord.ext import tasks

# 抓時間 & 設定時區
from datetime import time, datetime
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


@cactpot_task.before_loop
async def before_cactpot():
    await bot.wait_until_ready()


@reset_notice_task.before_loop
async def before_reset_notice():
    await bot.wait_until_ready()
    

@bot.event
async def on_ready():
    print(f"已登入：{bot.user}")

    if not cactpot_task.is_running():
        cactpot_task.start()
    
    if not reset_notice_task.is_running():
        reset_notice_task.start()
bot.run(token)
