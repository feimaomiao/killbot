import asyncio
import datetime
import difflib
import json
import logging
import os
from copy import deepcopy as dc
from os.path import isfile
from time import time as timetime
from hashlib import sha256

import discord
import requests
from discord import Embed as discordembed
from discord.ext import commands, tasks
from lzl import lzlist

from cogs import *
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
JSONLINK = os.getenv("JSONLINK")

logging.basicConfig(level=logging.INFO)
bot = commands.Bot(command_prefix=commands.when_mentioned_or('>'),
                   fetch_offline_members=False)

bot.remove_command("help")

configsonline = requests.get(JSONLINK).json()[0]
configs = dc({
    k: v
    for k, v in configsonline.items()
    if k not in ("_id", "_createdOn", "latest_eventid")
})
global last_id
last_id = configsonline["_id"]
global latest_eventid
latest_eventid = configsonline["latest_eventid"]
with open("default_cfg_template.json") as defcfgfile:
    defaultconfigs = json.load(defcfgfile)
global followingparties
followingparties = configs["GENERAL"]["trackingguild"] + configs["GENERAL"][
    "trackingplayer"]
with open("patchnotes") as patchnotesfile:
    patchnotes = patchnotesfile.read()
    shakey = sha256(patchnotes.encode()).hexdigest()
kb = killboard(latest_eventid)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="the killboard"))
    print(f"UPDATE LOG Hash: {shakey}")


@bot.command(name="update")
async def updatedmessage(client, key):
    if key != shakey:
        return await client.send("Wrong key entered!")
    for guilds in [c for c in configs if c != 'GENERAL']:
        if configs[guilds]["sendchannel"] == "0":
            continue
        channel = discord.utils.find(
            lambda x: x.id == int(configs[guilds]["sendchannel"]),
            bot.get_all_channels())
        try:
            await channel.trigger_typing()
            await channel.send(patchnotes)
        except AttributeError:
            continue
    return


# set loop to 150 seconds per update
@tasks.loop(seconds=150)
async def loadimages():
    try:
        for kills in await kb.newkills():
            k = kill(kills)
            await k.draw()
            # loop through guilds
            embedder, fileobj, fileloc = None, None, None
            for guilds in [c for c in configs if c != "GENERAL"]:
                if configs[guilds]["sendchannel"] == 0:
                    continue
                if kb.qualify(configs[guilds], dc(kills)):
                    embedder, fileobj, fileloc = k.create_embed(
                        configs[guilds]["trackingplayer"] +
                        configs[guilds]["trackingguild"])
                    while not isfile(fileloc):
                        await k.draw()
                    # load send channel
                    channel = discord.utils.find(
                        lambda x: x.id == int(configs[guilds]["sendchannel"]),
                        bot.get_all_channels())
                    if not channel:
                        continue
                    await channel.trigger_typing()
                    await channel.send(file=fileobj, embed=embedder)
            # Deletes file
            try:
                print(
                    f"{fileloc} deleted: {timetime()-k.starttime} seconds used")
                os.remove(fileloc)
            except TypeError:
                continue
            del k
        generalconfigs()
        print("Finished")
        return
    except Exception as e:
        print(type(e), e)


# Send help
@bot.command(name="help")
async def help(client):
    string = """\
```Commands for killbot:
Prefix: [>]

help:                           Sends this message

track (guild|player) name       Tracks and sends a kill by the given guild/player [killer/victim]
! May take some time as the server has to search for new values
for example: 
">track player feimaomiao"
">track elevate"

untrack (guild|player) name     Stops tracking that guild/player anymore
! May take some time as the server has to search for new values
for example:
">untrack player feimaomiao"
">untrack guild elevate"

minfame fame:                   set minimum fame to trigger a kill to be sent
for example:
">minfame 1000000"

list:                           list all currently tracking players and the guilds
">list"
```"""
    await client.send(string)


# When the bot joins a guild
@bot.event
async def on_guild_join(guild=None):
    # deepcopy because it if not its going to make copies and send more than one more time in one guild
    configs.update({"a" + str(guild.id): dc(defaultconfigs)})
    # Log join guild
    logging.info("Joined guild {} at {}".format(
        guild.id,
        datetime.datetime.now().strftime("%x %X:%f")))
    # Send guild
    await [i for i in guild.channels if type(i) == discord.TextChannel][0].send(
        "Thanks for inviting me to the channel.\n Please type `>help` to see what I can do!"
    )
    # update configs
    generalconfigs()
    return


# When guild is removed
@bot.event
async def on_guild_remove(guild=None):
    # delete guild info
    del configs["a" + str(guild.id)]
    logging.info("Left guild {} at {}".format(
        guild.id,
        datetime.datetime.now().strftime("%x %X:%f")))
    generalconfigs()


# Write configs to the currentconfigs
def updateconfigs(currconfigs):
    global last_id
    global configs
    requests.delete(f"{JSONLINK}/{last_id}")
    send = requests.post(JSONLINK,
                         json=currconfigs,
                         headers={"content-type": "application/json"})
    configsonline = requests.get(JSONLINK).json()[0]
    configs = dc({
        k: v
        for k, v in configsonline.items()
        if k not in ("_id", "_createdOn", "latest_eventid")
    })
    last_id = configsonline["_id"]
    return


# Set channel
@bot.command(name="channel")
async def channel(client, channel_name):
    # see if channelname is an id
    channel = [i for i in client.guild.channels if str(i.id) == channel_name]
    # get closest match to channel
    try:
        if len(channel) == 0:
            channel = difflib.get_close_matches(
                channel_name, [i.name for i in client.guild.channels])
            channel = [
                i for i in client.guild.text_channels if i.name == channel[0]
            ]
    except Exception as e:
        print(type(e), e)
        await client.send(
            "Channel cannot be set due to unknown error.\nSend channel is currently configured to this channel!"
        )
        configs[f"a{client.guild.id}"]["sendchannel"] = str(client.channel.id)
        return generalconfigs()
    # if channel is not found
    if len(channel) == 0:
        await client.send(
            "Whoops! I cannot find this server, are you sure you entered the right name?\nYou can also enter a channel id by putting the channel id in!"
        )
    else:
        try:
            await channel[0].trigger_typing()
            # set configs id
            configs[f"a{client.guild.id}"]["sendchannel"] = str(channel[0].id)
            # make a test send
            await client.send(
                "If you do not see the test message, you probably have to fix the channel settings!"
            )
            await channel[0].send(
                "This is a test\nIf you see this message, I have the permission to send messages in this channel!"
            )
        except discord.errors.Forbidden:
            await client.send(
                "Channel cannot be set as I do not have the permission on that channel!\nSend channel is currently configured to this channel"
            )
            configs[f"a{client.guild.id}"]["sendchannel"] = str(
                client.channel.id)
    return generalconfigs()


# Track a player or guild
@bot.command(name="track")
async def track(client, flwtype, *name):
    # follow type must be guild or player
    if flwtype not in ["guilds", "players", "guild", "player"]:
        await client.send(
            "The tracking object cannot be accessed.\nMake sure if you are tracking a guild or a player!"
        )
        return
    # Track guild
    if flwtype.startswith("guild"):
        message, trackingid, trackingname, found = await kb.search(
            "guilds", name)
        if found:
            configs[f'a{client.guild.id}']["trackingguild"].append(trackingid)
            configs[f'a{client.guild.id}']["trackingguildname"].append(
                trackingname)
    else:
        message, trackingid, trackingname, found = await kb.search(
            "players", name)
        if found:
            configs[f'a{client.guild.id}']["trackingplayer"].append(trackingid)
            configs[f'a{client.guild.id}']["trackingplayername"].append(
                trackingname)
    await client.trigger_typing()
    await client.send(message)
    generalconfigs()
    return


# untrack a guild or player
@bot.command(name="untrack")
async def untrack(client, flwtype, *name):
    if flwtype not in ["guilds", "players", "guild", "player"]:
        await client.send(
            "The tracking object cannot be accessed.\nMake sure if you are tracking a guild or a player!"
        )
        return
    # set guild
    guildloc = configs[f'a{client.guild.id}']
    if flwtype.startswith("guild"):
        message, trackingid, trackingname, found = await kb.search(
            "guilds", name)
        # check if tracking is found and the guild is currently following the given player/guild
        if found and trackingid in configs[
                "a" + str(client.guild.id)]["trackingguild"]:
            guildloc["trackingguild"].pop(
                guildloc["trackingguild"].index(trackingid))
            guildloc["trackingguildname"].pop(
                guildloc["trackingguildname"].index(trackingname))
            # set message
            message = f"{trackingname} is removed from your tracking list"
        else:
            # tracking name is not tracking
            message = f"{trackingname} is not found in your tracking datas"
    else:
        message, trackingid, trackingname, found = await kb.search(
            "players", name)
        if found and trackingid in configs[
                "a" + str(client.guild.id)]["trackingplayer"]:
            guildloc["trackingplayer"].pop(
                guildloc["trackingplayer"].index(trackingid))
            guildloc["trackingplayername"].pop(
                guildloc["trackingplayername"].index(trackingname))
            message = f"{trackingname} is removed from your tracking list"
        else:
            message = f"{trackingname} is not found in your tracking datas"
    await client.send(message)
    return generalconfigs()


@bot.command(name="minfame")
async def setminfame(client, fame, *others):
    await client.trigger_typing()
    if not fame.isdigit():
        await client.send("Make sure the fame is an integer!")
        return
    if int(fame) < 1000000:
        await client.send(
            "To prevent spam and preserve operating power for the killbot, minfame must be at least 1000000!"
        )
        fame = "1000000"
    configs[f'a{client.guild.id}']["minimumkillfame"] = int(fame)
    await client.send("Minimum kill fame is set to {}".format(fame))
    generalconfigs()
    return


# load general configurations
def generalconfigs():
    global followingparties
    # Makes the following key unique
    for k, v in configs.items():
        if k == "GENERAL":
            continue
        for key, value in v.items():
            if type(value) != list:
                continue
            v[key] = lzlist(value).unique
    # Add a list of total tracking guild.
    configs["GENERAL"]["trackingguild"] = list(
        set(
            lzlist(i["trackingguild"]
                   for i in [v for k, v in configs.items()
                             if k != "GENERAL"]).join_all()))
    configs["GENERAL"]["trackingplayer"] = list(
        set(
            lzlist(i["trackingplayer"]
                   for i in [v for k, v in configs.items()
                             if k != "GENERAL"]).join_all()))
    # get the smallest kill fame in all guilds
    try:
        configs["GENERAL"]["minimumkillfame"] = min([
            i["minimumkillfame"]
            for i in [v for k, v in configs.items() if k != "GENERAL"]
        ])
    # No guild has set a minimum fame yet// have not joined any guild
    except ValueError:
        pass
    # Set a list of tracking guilds and players to the kb object
    kb.tracking = configs["GENERAL"]["trackingplayer"] + configs["GENERAL"][
        "trackingguild"]
    # Set the minimum kill fame of the killboard
    kb.minkillfame = configs["GENERAL"]["minimumkillfame"]
    # update the following parties for the colors!
    followingparties = configs["GENERAL"]["trackingguild"] + configs["GENERAL"][
        "trackingplayer"]
    #set a latest item
    configs["latest_eventid"] = kb.latest
    # dump everything into the configs file
    return updateconfigs(configs)


# send a list of following
@bot.command(name="list")
async def list_following(client):
    nl = "\n"
    lss = f"```css{nl*2}Following Guilds:{nl}{nl.join([i for i in configs['a' +str(client.guild.id)]['trackingguildname']])}{nl*2}Following players:{nl}{nl.join([i for i in configs['a' +str(client.guild.id)]['trackingplayername']])}{nl*2}Minimum Fame for sending: {configs[f'a{client.guild.id}']['minimumkillfame']}```"
    return await client.send(lss)


@bot.command(name="uptime")
async def uptime(client):
    timediff = (datetime.datetime.now() - kb.starttime)
    await client.send("uptime: " + str(timediff))


generalconfigs()
loadimages.start()
bot.run(TOKEN)
