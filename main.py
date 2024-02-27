#!/usr/bin/env python3

"""
Discord twitter -> fx bot
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, TypedDict, Any
import re
import requests
import discord

# config, contains secrets
import config

twitter_url_regex = re.compile(
    r"(?<!<)https?://(?:mobile\.)?(?:twitter|x)\.com/([^/]+)/status/(\d+)(?!\S*>)", re.I
)

NagType = Enum(
    "NagType",
    [
        # normal fx link
        "FULL",
        # g.fx media embed
        "VIDEO",
        # g.fx/photos/2 media embed
        "SECOND_IMAGE",
        # g.fx media embed
        "MOSAIC",
    ],
)

nags: dict[int, discord.Message] = {}

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


class FxMedia(TypedDict):
    """
    Partial Media representation from Fx API
    """

    # we only care about how many media there are
    all: list[Any]


class FxTweet(TypedDict):
    """
    Partial Tweet representation from Fx API
    """

    media: Optional[FxMedia]


class FxResponse(TypedDict):
    """
    Top-level response from the Fx API
    """

    code: int
    message: str
    tweet: Optional[FxTweet]


def get_fx_nagtype(user: str, tid: str) -> Optional[NagType]:
    """
    Request additional data from FxTwitter
    to determine what embed type to use
    """
    try:
        response = requests.get(
            f"https://api.fxtwitter.com/{user}/status/{tid}", timeout=3
        )
        response.raise_for_status()
        fx_res: FxResponse = response.json()
        tweet = fx_res.get("tweet")
        if tweet is None:
            # tweet no longer exists
            return None
        media = tweet.get("media")
        if media is None:
            # text-only tweet
            return None
        media_all = media.get("all")
        if len(media_all) == 1:
            # original already embedded
            return None
        if len(media_all) == 2:
            # special case for 2-image tweets
            return NagType.SECOND_IMAGE
        # every other case
        return NagType.MOSAIC

    except requests.HTTPError:
        # can't access API, just be safe and respond with a mosaic
        return NagType.MOSAIC


@client.event
async def on_ready() -> None:
    """Log client information on start"""
    print("Logged on as", client.user)


async def nag(message: discord.Message, nag_type: NagType) -> None:
    """
    Post normal fxtwitter link in response to a native twitter link
    """
    tweets: list[tuple[str, str]] = twitter_url_regex.findall(message.content)
    base = "https://fxtwitter.com"
    modifier = ""
    if nag_type is not NagType.FULL:
        base = "https://g.fxtwitter.com"
        if nag_type is NagType.SECOND_IMAGE:
            modifier = "/photos/2"
    urls = [f"{base}/{user}/status/{tid}{modifier}" for user, tid in tweets]
    if should_spoiler(message):
        urls = [f"|| {url} ||" for url in urls]
    if urls:
        nags[message.id] = await message.reply("\n".join(urls), mention_author=False)
        if should_nag(message) is None:
            await unnag(message)


async def unnag(message: discord.Message) -> None:
    """
    Remove the fxtwitter link
    """
    if message.id in nags:
        guild_string = ""
        if message.guild is not None:
            guild_string = f"on {message.guild.id}"
        print(
            f"!! removing response to {message.id} in {message.channel.id}{guild_string}"
        )
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


def should_nag(message: discord.Message) -> Optional[NagType]:
    """
    Test whether we should respond to the message.

    Requires a native twitter link. Then, checks at least one of the following conditions is met:
    1. When Twitter embeds break, always reply
    2. Both channel and at least one embed are marked sensitive
    3. Embed is safe and there is a video
    """
    if not re.search(r"(//|mobile\.)(twitter|x)\.com", message.content):
        return None
    if not message.embeds:
        return NagType.FULL
    # sensitive check _must_ be done before other types
    # to prevent mixing NSFW and SFW links from embedding
    if any(_is_sensitive_tweet_embed(em) for em in message.embeds):
        channel = message.channel
        if channel.type in (discord.ChannelType.private, discord.ChannelType.group):
            # always allow NSFW in (group) DMs
            return NagType.FULL
        if (
            isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.ForumChannel,
                    discord.StageChannel,
                    discord.VoiceChannel,
                    discord.Thread,
                ),
            )
            and channel.is_nsfw()
        ):
            return NagType.FULL
        # nsfw in sfw channel, prevent embed
        print("Skipping NSFW embed in SFW channel")
        return None
    if any(_is_video_tweet(em) for em in message.embeds):
        return NagType.VIDEO
    # remaining case is POTENTIALLY multi-image, check fx API
    tweets: list[tuple[str, str]] = twitter_url_regex.findall(message.content)
    for user, tid in tweets:
        # if there's at least one, return the first nag type
        return get_fx_nagtype(user, tid)
    return None


def _is_video_tweet(embed: discord.Embed) -> bool:
    if embed.url is None:
        return False
    # use the proper regex
    # to not false match vx/fx when mixed with native
    is_twitter_embed = twitter_url_regex.match(embed.url) is not None
    if not is_twitter_embed:
        return False
    if embed.image.url is None:
        return False

    # native video embed now uses a thumbnail instead of broken video
    # URL begins with https://pbs.twimg.com/ext_tw_video_thumb/
    # or https://pbs.twimg.com/tweet_video_thumb/
    contains_video_thumbnail = "ext_tw_video_thumb" in embed.image.url
    contains_gif_thumbnail = "tweet_video_thumb" in embed.image.url
    return contains_video_thumbnail or contains_gif_thumbnail


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

    nag_type = should_nag(message)
    if nag_type is not None:
        await nag(message, nag_type)


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

    old_nag_type = should_nag(old)
    new_nag_type = should_nag(new)

    if new_nag_type is None:
        await unnag(old)
    elif new_nag_type != old_nag_type:
        # message edited with different link
        # or embed type changed
        if old_nag_type is not None:
            await unnag(old)
        await nag(new, new_nag_type)


@client.event
async def on_message_delete(message: discord.Message) -> None:
    """
    Follow original and delete the message
    """
    if message.id in nags:
        await unnag(message)


if __name__ == "__main__":
    client.run(config.TOKEN)
