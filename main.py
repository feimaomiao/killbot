import asyncio
import datetime
import difflib
import json
import logging
import os
import time
from copy import deepcopy as dc

import requests
from lzl import lzlist

import discord
from cogs import *
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
JSONLINK = os.getenv("JSONLINK")

logging.basicConfig(level=logging.INFO)
bot = commands.Bot(command_prefix=commands.when_mentioned_or('>'))

bot.remove_command("help")

kb = killboard()
configsonline = requests.get(JSONLINK).json()
configs = dc({
    k: v for k, v in configsonline[0].items() if k not in ["_id", "_createdOn"]
})
global last_id
last_id = configsonline[0]["_id"]
with open("default_cfg_template.json") as defcfgfile:
    defaultconfigs = json.load(defcfgfile)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(
        name="scanning the internet"))
    print("online")


# set loop to 5 minutes per update
@tasks.loop(minutes=5)
async def loadimages():
    try:
        if not kb.set:
            await kb.start()
        for kills in await kb.newkills():
            k = kill(kills)
            embedder, fileobj, fileloc = await k.embed()
            # loop through guilds
            for guilds in [c for c in configs if c != "GENERAL"]:
                if kb.qualify(configs[guilds], kills):
                    # load send channel
                    channel = discord.utils.find(
                        lambda x: x.id == int(configs[guilds]["sendchannel"]),
                        bot.get_all_channels())
                    print(configs[guilds]["sendchannel"])
                    print(channel)
                    await channel.trigger_typing()
                    await channel.send(file=fileobj, embed=embedder)
                    # fileobj is singleload only
                    embedder, fileobj, fileloc = k.reload()
            # Deletes file
            os.remove(fileloc)
            print("File deleted")
        return
    except Exception as e:
        print(e)


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
">track guild sex with ex"

untrack (guild|player) name     Stops tracking that guild/player anymore
! May take some time as the server has to search for new values
for example:
">untrack player feimaomiao"
">untrack guild sex with ex"

minfame fame:                   set minimum fame to trigger a kill to be sent
for example:
">minfame 1000000"

list:                           list all currently tracking players and the guilds
">list"```"""
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
    requests.delete(f"{JSONLINK}/{last_id}")
    send = requests.post(JSONLINK,
                         json=currconfigs,
                         headers={"content-type": "application/json"})
    configsonline = requests.get(JSONLINK).json()
    configs = dc({
        k: v
        for k, v in configsonline[0].items()
        if k not in ["_id", "_createdOn"]
    })
    last_id = configsonline[0]["_id"]
    return


# Set channel
@bot.command(name="channel")
async def channel(client, channel_name):
    # see if channelname is an id
    channel = [i for i in client.guild.channels if str(i.id) == channel_name]
    # get closest match to channel
    if len(channel) == 0:
        channel = difflib.get_close_matches(
            channel_name, [i.name for i in client.guild.channels])
        channel = [
            i for i in client.guild.text_channels if i.name == channel[0]
        ]
    # if channel is not found
    if len(channel) == 0:
        await client.send(
            "Whoops! I cannot find this server, are you sure you entered the right name?\nYou can also enter a channel id by putting the channel id in!"
        )
    else:
        print(channel[0].id)
        # set configs id
        configs[f"a{client.guild.id}"]["sendchannel"] = str(channel[0].id)
        await channel[0].trigger_typing()
        # make a test send
        await client.send(
            "If you do not see the test message, you probably have to fix the channel settings!"
        )
        await channel[0].send(
            "This is a test\nIf you see this message, I have the permission to send messages in this channel!"
        )
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
            guildloc["trackingguild"].pop(
                guildloc["trackingplayer"].index(trackingid))
            guildloc["trackingguild"].pop(
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
    # dump everything into the configs file
    return updateconfigs(configs)


# send a list of following
@bot.command(name="list")
async def list_following(client):
    nl = "\n"
    lss = f"```css{nl*2}Following Guilds:{nl}{nl.join([i for i in configs['a' +str(client.guild.id)]['trackingguildname']])}{nl*2}Following players:{nl}{nl.join([i for i in configs['a' +str(client.guild.id)]['trackingplayername']])}{nl*2}Minimum Fame for sending: {configs[f'a{client.guild.id}']['minimumkillfame']}```"
    return await client.send(lss)


generalconfigs()
loadimages.start()
bot.run(TOKEN)
