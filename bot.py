import discord
from discord.ext import commands
from datetime import datetime, timedelta
import sqlite3

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
voice_start_times = {}

def init_db():
    conn = sqlite3.connect("activity_weekly.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS messages (user_id INTEGER, date TEXT, count INTEGER DEFAULT 1)")
    cursor.execute("CREATE TABLE IF NOT EXISTS voice (user_id INTEGER, date TEXT, seconds INTEGER)")
    conn.commit()
    conn.close()

def add_message(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("activity_weekly.db")
    cursor = conn.cursor()
    cursor.execute("SELECT rowid FROM messages WHERE user_id = ? AND date = ?", (user_id, today))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE messages SET count = count + 1 WHERE rowid = ?", (row[0],))
    else:
        cursor.execute("INSERT INTO messages (user_id, date, count) VALUES (?, ?, 1)", (user_id, today))
    conn.commit()
    conn.close()

def add_voice_time(user_id, seconds):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("activity_weekly.db")
    cursor = conn.cursor()
    cursor.execute("SELECT rowid FROM voice WHERE user_id = ? AND date = ?", (user_id, today))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE voice SET seconds = seconds + ? WHERE rowid = ?", (seconds, row[0]))
    else:
        cursor.execute("INSERT INTO voice (user_id, date, seconds) VALUES (?, ?, ?)", (user_id, today, seconds))
    conn.commit()
    conn.close()

def get_weekly_stats(user_id):
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = sqlite3.connect("activity_weekly.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT SUM(count) FROM messages WHERE user_id = ? AND date >= ?", (user_id, seven_days_ago))
    msg_row = cursor.fetchone()
    messages = msg_row[0] if msg_row and msg_row[0] is not None else 0

    cursor.execute("SELECT SUM(seconds) FROM voice WHERE user_id = ? AND date >= ?", (user_id, seven_days_ago))
    voice_row = cursor.fetchone()
    seconds = voice_row[0] if voice_row and voice_row[0] is not None else 0

    conn.close()
    return messages, seconds

@bot.event
async def on_ready():
    init_db()
    print("Бот успешно запущен и готов к работе!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    add_message(message.author.id)
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    user_id = member.id
    now = datetime.now()
    if before.channel is None and after.channel is not None:
        voice_start_times[user_id] = now
    elif before.channel is not None and after.channel is None:
        start_time = voice_start_times.pop(user_id, None)
        if start_time:
            add_voice_time(user_id, int((now - start_time).total_seconds()))
    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        start_time = voice_start_times.pop(user_id, None)
        if start_time:
            add_voice_time(user_id, int((now - start_time).total_seconds()))
        voice_start_times[user_id] = now

def get_medal(index):
    if index == 1: return "🥇"
    if index == 2: return "🥈"
    if index == 3: return "🥉"
    return "#" + str(index)

@bot.command(name="стата")
async def show_stats(ctx):
    user_id = ctx.author.id
    messages, total_seconds = get_weekly_stats(user_id)
    if ctx.author.voice and user_id in voice_start_times:
        total_seconds += int((datetime.now() - voice_start_times[user_id]).total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    embed = discord.Embed(title="✨ ВАША АКТИВНОСТЬ ЗА 7 ДНЕЙ ✨", color=0x2b2d31)
    if ctx.author.display_avatar:
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
    
    desc = "👤 **Пользователь:** " + ctx.author.mention + "\n\n"
    desc += "💬 **Текстовая активность:**\n` " + str(messages) + " сообщений `\n\n"
    desc += "🔊 **Время в голосовых:**\n` " + str(hours) + " ч. " + str(minutes) + " мин. `"
    
    embed.description = desc
    await ctx.send(embed=embed)

@bot.command(name="неделя")
async def show_leaderboard(ctx):
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = sqlite3.connect("activity_weekly.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, SUM(count) FROM messages WHERE date >= ? GROUP BY user_id ORDER BY SUM(count) DESC LIMIT 5", (seven_days_ago,))
    top_messages = cursor.fetchall()
    cursor.execute("SELECT user_id, SUM(seconds) FROM voice WHERE date >= ? GROUP BY user_id ORDER BY SUM(seconds) DESC LIMIT 5", (seven_days_ago,))
    top_voice = cursor.fetchall()
    conn.close()

    embed = discord.Embed(title="🏆 ЛИДЕРБОРД АКТИВНОСТИ ЗА НЕДЕЛЮ", color=0xffd700)
    embed.description = "Статистика за последние 7 дней.\n" + "─" * 35

    msg_text = ""
    for i, row in enumerate(top_messages, 1):
        member = ctx.guild.get_member(row[0])
        name = member.display_name if member else "Пользователь ушел"
        medal = get_medal(i)
        msg_text += medal + " **" + name + "**\n┗━━ ` " + str(row[1]) + " ` сообщ.\n"
    embed.add_field(name="💬 ТОП ПО СООБЩЕНИЯМ", value=msg_text if msg_text else "*Пока нет сообщений*", inline=False)

    voice_text = ""
    for i, row in enumerate(top_voice, 1):
        member = ctx.guild.get_member(row[0])
        name = member.display_name if member else "Пользователь ушел"
        medal = get_medal(i)
        h = row[1] // 3600
        m = (row[1] % 3600) // 60
        voice_text += medal + " **" + name + "**\n┗━━ ` " + str(h) + " ч. " + str(m) + " мин. `\n"
    embed.add_field(name="🔊 ТОП ПО ГОЛОСУ (ВОЙС)", value=voice_text if voice_text else "*Пока никто не сидел*", inline=False)

    await ctx.send(embed=embed)

import os
# Бот будет брать токен из скрытых настроек сервера Render
bot.run(os.getenv("BOT_TOKEN"))

