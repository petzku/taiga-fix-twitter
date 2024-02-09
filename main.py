#!/usr/bin/env python3

"""
Discord twitter -> vx bot
"""
from __future__ import annotations
import re
import discord

# config, contains secrets
import config

twitter_url_regex = re.compile(
    r"(?<!<)https?://(?:mobile\.)?(?:twitter|x)\.com/([^/]+)/status/(\d+)(?!\S*>)", re.I
)

nags: dict[int, discord.Message] = {}

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready() -> None:
    """Log client information on start"""
    print("Logged on as", client.user)


async def nag(message: discord.Message) -> None:
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


async def unnag(message: discord.Message) -> None:
    """
    Remove the vxtwitter link
    """
    print(
        f"!! removing response to {message.id} in {message.channel} on {message.guild}"
    )
    if message.id in nags:
        await nags[message.id].delete()


def _allowed_server(guild_id: int) -> bool:
    return not guild_id in config.SERVER_BLACKLIST


def _allowed_user(user_id: int) -> bool:
    # accept any users if whitelist is empty
    return not config.USER_IDS or user_id in config.USER_IDS


def is_allowed_reply(message: discord.Message) -> bool:
    """
    Make sure:
    - User is allowed (if set)
    - Server is not blacklisted
    """
    if not _allowed_user(message.author.id):
        # ignore unallowed user
        return False
    if message.guild is None:
        # private message
        return True
    # server message
    return _allowed_server(message.guild.id)


def should_spoiler(message: discord.Message) -> bool:
    """Rough detection of spoilered content"""
    return "||" in message.content


def should_nag(message: discord.Message) -> bool:
    """
    Test whether we should respond to the message.

    Requires a native twitter link. Then, checks at least one of the following conditions is met:
    1. When Twitter embeds break, always reply
    2. Both channel and at least one embed are marked sensitive
    3. Embed is safe and there is a video
    """
    if not re.search(r"(//|mobile\.)(twitter|x)\.com", message.content):
        return False
    if not message.embeds:
        return True
    # sensitive check _must_ be done before other types
    # to prevent mixing NSFW and SFW links from embedding
    if any(_is_sensitive_tweet_embed(em) for em in message.embeds):
        channel = message.channel
        if channel.type in (discord.ChannelType.private, discord.ChannelType.group):
            # always allow NSFW in (group) DMs
            return True
        if hasattr(channel, "nsfw"):
            # .nsfw seems to not exist on some channel types
            # and discord.py type narrowing is limited
            # so this will have to do
            return getattr(channel, "nsfw") is True
    if any(_is_video_tweet(em) for em in message.embeds):
        return True
    return False


def _is_video_tweet(embed: discord.Embed) -> bool:
    if embed.url is None:
        return False
    # use the proper regex
    # to not false match vx/fx when mixed with native
    is_twitter_embed = twitter_url_regex.match(embed.url) is not None
    if not is_twitter_embed:
        return False
    if embed.image.url is None:
        return True

    # native video embed now uses a thumbnail instead of broken video
    # URL begins with https://pbs.twimg.com/ext_tw_video_thumb/
    contains_video_thumbnail = "ext_tw_video_thumb" in embed.image.url
    return contains_video_thumbnail


def _is_sensitive_tweet_embed(embed: discord.Embed) -> bool:
    if embed.url is None:
        return False
    # use the proper regex
    # to not false match vx/fx when mixed with native
    is_twitter_embed = twitter_url_regex.match(embed.url) is not None
    if not is_twitter_embed:
        return False
    if embed.image.url is None and embed.description is None:
        # Twitter returns a fake rich embed
        # When media is sensitive
        return True
    return False


@client.event
async def on_message(message: discord.Message) -> None:
    """
    Check every message send
    """
    if message.author.bot:
        # ignore bots and self
        return
    if not is_allowed_reply(message):
        return

    if should_nag(message):
        await nag(message)


@client.event
async def on_message_edit(old: discord.Message, new: discord.Message) -> None:
    """
    Sometimes embeds aren't ready when we see the message.
    In this case, we should get an on_message_edit once it is.
    """
    if new.author.bot:
        # ignore bots and self
        return
    if not is_allowed_reply(new):
        return

    if not should_nag(new):
        await unnag(old)


@client.event
async def on_message_delete(message: discord.Message) -> None:
    """
    Follow original and delete the message
    """
    if message.id in nags:
        await unnag(message)


if __name__ == "__main__":
    client.run(config.TOKEN)
