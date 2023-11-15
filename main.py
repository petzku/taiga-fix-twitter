#!/usr/bin/env python3

import discord
import re
import time

# config, contains secrets
import config

twitter_url_regex = re.compile(
    r"(?<!<)https?://(?:mobile\.)?(twitter|x)\.com/([^/]+)/status/(\d+)(?!\S*>)", re.I
)

nags = {}

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print("Logged on as", client.user)


async def nag(message):
    tweets = twitter_url_regex.findall(message.content)
    urls = [f"https://vxtwitter.com/{user}/status/{tid}" for user, tid in tweets]
    if should_spoiler(message):
        urls = [f"|| {url} ||" for url in urls]
    if urls:
        nags[message.id] = await message.reply("\n".join(urls), mention_author=False)
        if not should_nag(message):
            await unnag(message)


async def unnag(message):
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
    return _allowed_server(message.guild.id) and _allowed_user(message.author.id)


def should_spoiler(message):
    return "||" in message.content


def should_nag(message):
    if not (
        re.search("(\/\/|mobile\.)(twitter|x)\.com", message.content)
    ):
        return False
    if not message.embeds:
        return True
    if any(_is_video_tweet(em) for em in message.embeds):
        return True


def _is_video_tweet(embed):
    print(embed)
    return embed.video and (True if re.search("(x|twitter)\.com", embed.url) else False)


@client.event
async def on_message(message):
    # don't respond to ourselves
    if message.author == client.user:
        return
    if not is_allowed_reply(message):
        return

    if should_nag(message):
        await nag(message)


# sometimes embeds aren't ready when we see the message. in this case, we should get an on_message_edit once it is.
@client.event
async def on_message_edit(old, new):
    if new.author == client.user:
        return
    if not is_allowed_reply(new):
        return

    if not should_nag(new):
        await unnag(old)


@client.event
async def on_message_delete(message):
    if message.id in nags:
        await unnag(message)


if __name__ == "__main__":
    client.run(config.TOKEN)
