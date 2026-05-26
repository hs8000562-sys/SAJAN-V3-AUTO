import discord
from discord.ext import commands
import aiohttp
import json
import os
import asyncio
from datetime import datetime, UTC
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from dotenv import load_dotenv

# =========================
# LOAD ENV
# =========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_IDS_STR = os.getenv("1389248077503664239")
API_URL = os.getenv("http://panel.thug4ff.xyz:6044/like?uid=2760139717&region=ag&key=diboxe9744737")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN missing in .env")

if not OWNER_IDS_STR:
    raise ValueError("OWNER_IDS missing in .env")

if not API_URL:
    raise ValueError("API_URL missing in .env")

OWNER_IDS = [
    int(i.strip())
    for i in OWNER_IDS_STR.split(",")
    if i.strip().isdigit()
]

# =========================
# DATABASE
# =========================

DB_FILE = "database.json"


def load_db():

    if not os.path.exists(DB_FILE):

        return {
            "guilds": {},
            "users": {},
            "autolikes": [],
            "lastReset": None
        }

    with open(DB_FILE, "r") as f:

        try:
            return json.load(f)

        except json.JSONDecodeError:

            return {
                "guilds": {},
                "users": {},
                "autolikes": [],
                "lastReset": None
            }


def save_db(data):

    with open(DB_FILE, "w") as f:

        json.dump(data, f, indent=4)


db = load_db()

# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

scheduler = AsyncIOScheduler()
scheduler_started = False

# =========================
# HELPERS
# =========================

def is_owner(user_id):

    return user_id in OWNER_IDS


def get_region_display(region):

    regions = {
        "BD": "🇧🇩 Bangladesh",
        "SG": "🇸🇬 Singapore",
        "IND": "🇮🇳 India",
        "ID": "🇮🇩 Indonesia",
        "BR": "🇧🇷 Brazil",
        "TH": "🇹🇭 Thailand",
        "VN": "🇻🇳 Vietnam",
        "ME": "🇲🇪 MENA",
        "PK": "🇵🇰 Pakistan",
        "RU": "🇷🇺 Russia",
    }

    return regions.get(str(region).upper(), str(region))


# =========================
# REMOVE EXPIRED AUTOLIKES
# =========================

def remove_expired_autolikes():

    current_time = datetime.now(UTC).timestamp()

    before_count = len(db["autolikes"])

    db["autolikes"] = [

        al for al in db["autolikes"]

        if al.get("expireAt", 0) > current_time
    ]

    after_count = len(db["autolikes"])

    removed = before_count - after_count

    if removed > 0:

        print(f"Removed {removed} expired autolike(s).")

        save_db(db)


# =========================
# DAILY CREDIT RESET
# =========================

async def reset_daily_credits():

    print("Running daily credit reset...")

    ist = pytz.timezone("Asia/Kolkata")

    now = datetime.now(ist)

    today = now.strftime("%Y-%m-%d")

    if db.get("lastReset") == today:
        return

    for user_id, data in db.get("users", {}).items():

        max_credits = data.get("maxCredits", 0)

        data["credits"] = max_credits

    db["lastReset"] = today

    save_db(db)

    print("Credits reset complete.")


# =========================
# DAILY AUTOLIKE
# =========================

async def daily_autolike():

    remove_expired_autolikes()

    print("Running daily autolike...")

    autolikes = db.get("autolikes", [])

    guild_channels = []

    for g_id, g_data in db.get("guilds", {}).items():

        if g_data.get("autoLikeChannel"):

            guild_channels.append(
                g_data["autoLikeChannel"]
            )

    async with aiohttp.ClientSession() as session:

        for index, al in enumerate(autolikes, start=1):
           
            ts = al["expireAt"]

            expiry_date = datetime.fromtimestamp(
                ts,
                UTC
            ).strftime("%d/%m/%Y")

            uid = al["uid"]

            region = al["region"]

            try:

                url = (
                    f"your api url"
                    f"?uid={uid}"
                    f"&region={region.lower()}"
                    f"&key=your api key"
                )

                async with session.get(
                    url,
                    timeout=30
                ) as response:

                    data = await response.json()

                    print("API RESPONSE:", data)

                if response.status != 200:
                    continue

                added_by = al.get("addedBy", "Unknown")

                embed = discord.Embed(
                    title=f"Auto Like ({index}/{len(autolikes)})",
                    color=discord.Color.green()
                )

                if bot.user:

                    embed.set_thumbnail(
                        url=bot.user.display_avatar.url
                    )

                embed.description = (
                    f"> **Added By:** <@{added_by}>\n"
                    f"> **Nickname:** {data.get('player', {}).get('nickname', 'Unknown')}\n"
                    f"> **Region:** {get_region_display(data.get('player', {}).get('region', region))}\n"
                    f"> **Player UID:** {data.get('player', {}).get('uid', uid)}\n"
                    f"> **Like Before:** {data.get('likes', {}).get('before', 0)}\n"
                    f"> **Like Added:** +{data.get('likes', {}).get('added_by_api', 0)}\n"
                    f"> **Like After:** {data.get('likes', {}).get('after', 0)}\n"
                    f"> **Expires At:** {expiry_date}"
                )

                embed.set_footer(
                    text="DEVELOPED BY OLD  SAJAN"
                )

                for ch_id in guild_channels:

                    try:

                        channel = bot.get_channel(ch_id)

                        if channel:

                            await channel.send(embed=embed)

                    except Exception as e:

                        print(f"Channel Send Error: {e}")

            except Exception as e:

                print(f"AutoLike Error: {e}")

            await asyncio.sleep(1)


# =========================
# EVENTS
# =========================

@bot.event
async def on_ready():

    global scheduler_started

    print(f"Logged in as {bot.user}")

    try:

        synced = await bot.tree.sync()

        print(f"Synced {len(synced)} command(s)")

    except Exception as e:

        print(f"Sync Error: {e}")

    if scheduler_started:
        return

    npt = pytz.timezone("Asia/Kathmandu")

    trigger = CronTrigger(
        hour=6,
        minute=15,
        timezone=npt
    )

    scheduler.add_job(
        daily_autolike,
        trigger
    )

    scheduler.add_job(
        reset_daily_credits,
        trigger
    )

    scheduler.start()

    scheduler_started = True

    await reset_daily_credits()


# =========================
# COMMANDS
# =========================

@bot.hybrid_command(
    name="autolikechannelset",
    description="Set autolike channel"
)
async def autolikechannelset(ctx):

    if not is_owner(ctx.author.id):
        return

    if not ctx.guild:
        return

    g_id = str(ctx.guild.id)

    if g_id not in db["guilds"]:
        db["guilds"][g_id] = {}

    db["guilds"][g_id]["autoLikeChannel"] = ctx.channel.id

    save_db(db)

    await ctx.send("Autolike channel set.")


# =========================

@bot.hybrid_command(
    name="autolikechannelremove",
    description="Remove autolike channel"
)
async def autolikechannelremove(ctx):

    if not is_owner(ctx.author.id):
        return

    if not ctx.guild:
        return

    g_id = str(ctx.guild.id)

    if g_id in db["guilds"]:

        db["guilds"][g_id]["autoLikeChannel"] = None

    save_db(db)

    await ctx.send("Autolike channel removed.")


# =========================

@bot.hybrid_command(
    name="autolike",
    description="Add UID to daily autolike"
)
async def autolike(
    ctx,
    region: str,
    uid: str,
    days: int
):

    if not is_owner(ctx.author.id):
        return

    if days <= 0:

        return await ctx.send(
            "Days must be greater than 0."
        )

    region = region.upper()

    for al in db["autolikes"]:

        if al["uid"] == uid and al["region"] == region:

            return await ctx.send(
                "UID already exists."
            )

    expire_time = (
        datetime.now(UTC).timestamp()
        + (days * 86400)
    )

    db["autolikes"].append({
        "region": region,
        "uid": uid,
        "addedBy": str(ctx.author.id),
        "expireAt": expire_time
    })

    save_db(db)

    await ctx.send(
        f"Added `{uid}` ({region}) to autolike for `{days}` day(s)."
    )


# =========================

@bot.hybrid_command(
    name="autolikeview",
    description="View all autolike UIDs"
)
async def autolikeview(ctx):

    if not is_owner(ctx.author.id):
        return

    remove_expired_autolikes()

    autolikes = db.get("autolikes", [])

    if not autolikes:

        return await ctx.send(
            "No autolikes found."
        )

    embed = discord.Embed(
        title="AutoLike Database",
        color=discord.Color.purple()
    )

    text = ""

    for index, al in enumerate(autolikes, start=1):

        remaining_days = max(
            0,
            int(
                (
                    al.get("expireAt", 0)
                    - datetime.now(UTC).timestamp()
                ) / 86400
            )
        )

        text += (
            f"**{index}.** "
            f"UID: `{al['uid']}` | "
            f"Region: `{al['region']}` | "
            f"Days Left: `{remaining_days}`\n"
        )

    embed.description = text

    embed.set_footer(
        text=f"Total AutoLikes: {len(autolikes)}"
    )

    await ctx.send(embed=embed)


# =========================

@bot.hybrid_command(
    name="autolikeremove",
    description="Remove UID from autolike"
)
async def autolikeremove(
    ctx,
    region: str,
    uid: str
):

    if not is_owner(ctx.author.id):
        return

    region = region.upper()

    found = None

    for al in db["autolikes"]:

        if al["uid"] == uid and al["region"] == region:

            found = al
            break

    if not found:

        return await ctx.send(
            "UID not found in autolike database."
        )

    db["autolikes"].remove(found)

    save_db(db)

    await ctx.send(
        f"Removed UID `{uid}` ({region}) from autolike."
    )


# =========================
# ERROR HANDLER
# =========================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        return

    print(error)


# =========================
# RUN BOT
# =========================

bot.run(TOKEN)
