#!/usr/bin/env python3

"""
Discord twitter -> vx bot
"""
import re
import discord

# config, contains secrets
import config

twitter_url_regex = re.compile(
    r"(?<!<)https?://(?:mobile\.)?(?:twitter|x)\.com/([^/]+)/status/(\d+)(?!\S*>)", re.I
)

nags = {}

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    """Log client information on start"""
    print("Logged on as", client.user)


async def nag(message):
    """
    Post vxtwitter link in response to a native twitter link
    """
    tweets = twitter_url_regex.findall(message.content)
    urls = [f"https://vxtwitter.com/{user}/status/{tid}" for user, tid in tweets]
    if should_spoiler(message):
        urls = [f"|| {url} ||" for url in urls]
    if urls:
        nags[message.id] = await message.reply("\n".join(urls), mention_author=False)
        if not should_nag(message):
            await unnag(message)


async def unnag(message):
    """
    Remove the vxtwitter link
    """
    print(
        f"!! removing response to {message.id} in {message.channel} on {message.guild}"
    )
    if message.id in nags:
        await nags[message.id].delete()


def _allowed_server(guild_id):
    return not guild_id in config.SERVER_BLACKLIST


def _allowed_user(user_id):
    # accept any users if whitelist is empty
    return not config.USER_IDS or user_id in config.USER_IDS


def is_allowed_reply(message):
    """
    Make sure:
    - Server is not blacklisted
    - User is allowed (if set)
    """
    return _allowed_server(message.guild.id) and _allowed_user(message.author.id)


def should_spoiler(message):
    """Rough detection of spoilered content"""
    return "||" in message.content


def should_nag(message):
    """
    Only reply if:
    1. There exists a native twitter link
    2. There is no existing embed
    3. There is a video in the tweet
    """
    if not re.search(r"(//|mobile\.)(twitter|x)\.com", message.content):
        return False
    if not message.embeds:
        return True
    if any(_is_video_tweet(em) for em in message.embeds):
        return True
    return False


def _is_video_tweet(embed):
    print(embed)
    return embed.video and ("twitter.com" in embed.url or "x.com" in embed.url)


@client.event
async def on_message(message):
    """
    Check every message send
    """
    if message.author == client.user:
        return
    if not is_allowed_reply(message):
        return

    if should_nag(message):
        await nag(message)


@client.event
async def on_message_edit(old, new):
    """
    Sometimes embeds aren't ready when we see the message.
    In this case, we should get an on_message_edit once it is.
    """
    if new.author == client.user:
        return
    if not is_allowed_reply(new):
        return

    if not should_nag(new):
        await unnag(old)


@client.event
async def on_message_delete(message):
    """
    Follow original and delete the message
    """
    if message.id in nags:
        await unnag(message)


if __name__ == "__main__":
    client.run(config.TOKEN)
