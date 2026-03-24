import os

from dotenv import load_dotenv
load_dotenv()

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



@tasks.loop(time=time(hour=11, minute=30, tzinfo=TAIWAN_TZ))
async def cactpot_task():
    now = datetime.now(TAIWAN_TZ)

    if now.weekday() == 1:  # 星期六
        print("該提醒了")
        # 在特定頻道PING特定身分組
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        await channel.send(f"<@&{TARGET_ROLE_ID}> 記得去抽獎！")

@cactpot_task.before_loop
async def before():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    print(f"已登入：{bot.user}")

    if not cactpot_task.is_running():
        cactpot_task.start()

bot.run(token)