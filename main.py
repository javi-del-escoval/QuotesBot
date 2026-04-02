import discord
from discord.ext import commands, tasks
import requests
import os
import io
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SHEETS_API_URL = os.getenv("SHEETS_API_URL")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- STATE ---
posting_enabled = False
target_channel_id = None

# --- UTILITY ---
async def send_quote_with_media(channel, data):
    try:
        quote_text = f"**{data['quote']}**"
        media_url = data.get("media_link")

        # No media → just send text
        if not media_url:
            await channel.send(quote_text)
            return

        # Download media
        res = requests.get(media_url)

        if res.status_code != 200:
            await channel.send(quote_text + "\n(Failed to load media)")
            return

        file_bytes = io.BytesIO(res.content)

        # Try to infer filename
        filename = media_url.split("/")[-1].split("?")[0]
        if not filename:
            filename = "media"

        discord_file = discord.File(file_bytes, filename=filename)

        await channel.send(content=quote_text, file=discord_file)

    except Exception as e:
        print("Media send error:", e)
        await channel.send(f"**{data['quote']}**")


# --- BACKGROUND TASK ---
@tasks.loop(hours=24)  # adjust frequency here
async def auto_post_quote():
    global posting_enabled, target_channel_id

    if not posting_enabled or not target_channel_id:
        return

    channel = bot.get_channel(target_channel_id)
    if not channel:
        return

    try:
        res = requests.get(f"{SHEETS_API_URL}?action=getRandom")
        data = res.json()

        if "error" in data:
            return

        message = f"**{data['quote']}**"
        if data["media_link"]:
            message += f"\n{data['media_link']}"

        await channel.send(message)
        #await send_quote_with_media(channel, data)

    except Exception as e:
        print("Auto post error:", e)

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    auto_post_quote.start()


# --- COMMANDS ---
bot.remove_command("help")

@bot.command(name="help")
async def help_command(ctx, command_name: str = None):
    # --- GENERAL HELP ---
    if command_name is None:
        embed = discord.Embed(
            title="Bot Commands",
            description="Use `!help <command>` for more details",
            color=discord.Color.blue()
        )

        for command in bot.commands:
            if command.hidden:
                continue

            try:
                can_run = await command.can_run(ctx)
            except:
                can_run = False

            if not can_run:
                continue

            name = f"!{command.name}"
            if command.signature:
                name += f" {command.signature}"

            description = command.help or "No description provided."

            embed.add_field(
                name=name,
                value=description,
                inline=False
            )

        await ctx.send(embed=embed)
        return

    # --- SPECIFIC COMMAND HELP ---
    command = bot.get_command(command_name)

    if command is None:
        await ctx.send(f"Command `{command_name}` not found.")
        return

    try:
        can_run = await command.can_run(ctx)
    except:
        can_run = False

    if not can_run:
        await ctx.send("You don't have permission to use this command.")
        return

    embed = discord.Embed(
        title=f"!{command.name}",
        color=discord.Color.green()
    )

    # Description
    embed.add_field(
        name="Description",
        value=command.help or "No description provided.",
        inline=False
    )

    # Usage
    usage = f"!{command.name}"
    if command.signature:
        usage += f" {command.signature}"

    embed.add_field(
        name="Usage",
        value=f"`{usage}`",
        inline=False
    )

    # Aliases (if any)
    if command.aliases:
        embed.add_field(
            name="Aliases",
            value=", ".join(command.aliases),
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(
    help="Enable automatic daily quote posting in the current channel (admin only).",
    brief="Enable auto-posting",
    usage="")
@commands.has_permissions(administrator=True)
async def enablequotes(ctx):
    global posting_enabled, target_channel_id

    posting_enabled = True
    target_channel_id = ctx.channel.id

    await ctx.send("Auto quote posting ENABLED in this channel.")

@bot.command(
    help="Disable automatic quote posting (admin only).",
    brief="Disable auto-posting",
    usage="")
@commands.has_permissions(administrator=True)
async def disablequotes(ctx):
    global posting_enabled

    posting_enabled = False

    await ctx.send("Auto quote posting DISABLED.")

@bot.command(
    help="Fetch and display a random quote, then it's deleted from the pool",
    brief="Fetch and display a random quote.",
    usage="")
async def quote(ctx):
    try:
        res = requests.get(f"{SHEETS_API_URL}?action=getRandom")
        data = res.json()

        if "error" in data:
            await ctx.send("No quotes available.")
            return

        message = f"**{data['quote']}**"
        if data["media_link"]:
            message += f"\n{data['media_link']}"

        await ctx.send(message)
        #await send_quote_with_media(ctx.channel, data)

    except Exception as e:
        await ctx.send("Error fetching quote.")
        print(e)

@bot.command(
    help="Add a new quote. Format: !addquote quote text | optional_media_link",
    brief="Add a new quote.",
    usage="<quote_text> | [media_link]")
async def addquote(ctx, *, content):
    try:
        if "|" in content:
            quote_text, media_link = map(str.strip, content.split("|", 1))
        else:
            quote_text = content
            media_link = ""

        payload = {
            "action": "add",
            "quote": quote_text,
            "media_link": media_link
        }

        res = requests.post(SHEETS_API_URL, json=payload)

        if res.status_code == 200:
            await ctx.send("Quote added.")
        else:
            await ctx.send("Failed to add quote.")

    except Exception as e:
        await ctx.send("Error adding quote.")
        print(e)


bot.run(DISCORD_TOKEN)