import asyncio
import datetime
import json
import logging
import os
from time import time as timetime
from collections import Counter
from copy import deepcopy as dc
from io import BytesIO
from random import choice as randchoice
from random import randrange as rrange
from re import match, sub
from statistics import mean as avg

import aiohttp
import requests
from bs4 import BeautifulSoup as bs
from discord import Embed as discordembed
from discord import File as discordfile
from lzl import lzfloat, lzint, lzlist
from PIL import Image as img
from PIL import ImageDraw as imgdraw
from PIL import ImageFont as imgfont

# Set color variables
BACKGROUND = (10, 10, 10)
BLUE = (0, 255, 255)
RED = (255, 211, 0)
WHITE = (255, 255, 255)

# set font variables
defaultfont = imgfont.truetype("fonts/death.ttf", 70)
namesfont = imgfont.truetype("fonts/lk.ttf", 70)
namesfont_small = imgfont.truetype("fonts/guild.ttf", 50)
systemfont = imgfont.truetype("fonts/systemtext.ttf", 35)
largesystemfont = imgfont.truetype("fonts/systemtext.ttf", 60)
infotext = imgfont.truetype("fonts/info.ttf", 35)

# set formatted items used for items_get function
formatteditems = requests.get(
    "https://raw.githubusercontent.com/broderickhyman/ao-bin-dumps/master/formatted/items.json"
).json()

# get accurate plotting locations and names.
with open("data.json") as file:
    data = json.load(file)

# possibleprefixes is used for formatting the embed
with open("possibleprefixes.json") as file:
    prefixes = json.load(file)


# substituting useless items in the item name
def substitute(name):
    # Crystal league tokens
    m = match(r"T4_TOKEN_CRYSTALLEAGUE_LVL_(\d{1,2})_S(\d{1,2})", name)
    # Trade missions
    k = match(r"QUESTITEM_CARAVAN_TRADEPACK_([A-Z]{5,8})_(LIGHT|MEDIUM|HEAVY)",
              name)
    # HCE Maps
    h = match(r"QUESTITEM_EXP_TOKEN_D(\d{1,2})_T\d.+", name)
    if m:
        return f"S{m.group(2)} Crystal League Token (Lvl. {m.group(1)})"
    elif k:
        location = {
            "SWAMP": "Thetford",
            "FOREST": "Lymhurst",
            "STEPPE": "Bridgewatch",
            "HIGHLAND": "Martlock",
            "MOUNTAIN": "Fort Sterling"
        }[k.group(1)]
        tier = {"LIGHT": 1, "MEDIUM": 2, "HEAVY": 3}[k.group(2)]
        return f"Tier {tier} {location}'s Unsuspicious Box"
    elif h:
        return f"HCE Map (Lvl. {h.group(1)})"
    ls = [
        "Novice's ", "Journeyman's ", "Adept's ", "Expert's ", "Master's ",
        "Grandmaster's ", "Elder's ", "Uncommon ", "Rare ", "Exceptional ",
        "Novice ", "Journeyman ", "Adept ", "Expert ", "Master ",
        "Grandmaster ", "Elder ", "Major ", "Minor ", "Danglemouth "
    ]
    for items in ls:
        name = sub(items, "", name)
    return name


# get tier of items
def loadtier(i):
    tier = None
    try:
        tier = match(r"T([1-8]).*", i).group(1)
        enchantment = match(r".+@([1-3])", i).group(1)
    except AttributeError:
        enchantment = 0
    if not tier:
        return ""
    if not enchantment:
        enchantment = 0
    return f"[{tier}.{enchantment}]"


# Return item name from given unique key
def items_get(items, quality=1):
    try:
        return loadtier(items) + substitute([
            i["LocalizedNames"]["EN-US"]
            for i in formatteditems
            if i["UniqueName"] == str(items)
        ][0]) + '{}'.format({
            0: "",
            1: "(NM)",
            2: "(GD)",
            3: "(OT)",
            4: "(EX)",
            5: "(MP)"
        }[quality])
    except Exception as e:
        return substitute(str(items))


# convert the transparent nodes into orange nodes like the background
# Parameters: imageobj, transparent color to be converted into.
def convert_to_transparent(imageobj, transparent):
    # convert image object into rgba format
    imageobj = imageobj.convert("RGBA")
    # get image data from the image object
    data = imageobj.getdata()
    newData = []
    # loop through data items
    for i in data:
        # i[3] is the alpha channel for the image
        if i[3] <= 10:
            newData.append(transparent)
        else:
            newData.append(i)
    # Convert the list of data into an image.
    imageobj.putdata(newData)
    return imageobj


# async function to check if itemid is a double handed weapon.
# parameter: name -> unique key of weapon
async def is_two_main_hand(name):
    async with aiohttp.ClientSession() as session:
        async with session.get(
                "https://www.albiononline2d.com/en/item/id/{}".format(
                    name)) as resp:
            return {
                k: v for k, v in lzlist([
                    i.string for i in bs(await resp.text(),
                                         features="html.parser").find_all("td")
                ]).split_by(2)
            }["Two Handed"] == "true"


# async function to get image from the given link
async def get_image(link, item, session, quality=1):
    async with session.get(link + item + f".png?quality={quality}") as resp:
        # use bytesio object to load the respond conetent from online∂
        # -> use image module to load the image from bytesio object
        # -> resize the image object to 180x180 size
        # -> convert the image to transparent
        try:
            tobyte = BytesIO(await resp.content.read())
            tobyte.seek(0)
            return convert_to_transparent(
                img.open(tobyte).resize((180, 180), img.ANTIALIAS), BACKGROUND)
        except Exception as e:
            print("Image error", e, link + item)
            await asyncio.sleep(1)
            return await get_image(link, item, session)


async def get_iw_json(items, session, count=0):
    # Lambda function to return the api link
    getlink = lambda x: "https://www.albion-online-data.com/api/v2/stats/prices/" + x + "?locations=Lymhurst,Martlock,Bridgewatch,FortSterling,Thetford,Caerleon"
    try:
        async with session.get(getlink(items)) as resp:
            return await resp.json()
    # happens when the returned item is 404 error
    except aiohttp.client_exceptions.ContentTypeError:
        if count == 0:
            logging.warning("Gearworth Error {}".format(items))
        await asyncio.sleep(1)
        return await get_iw_json(items, session, count + 1)


# Function to get the average price from Lymhurst, Martlock, Bridgewatch, FortSterling and Thetford
def _getaverage(x, y):
    fnl = []
    for i in x:
        if i['quality'] == y and i["sell_price_min"] != 0:
            fnl.append(i["sell_price_min"])
    if len(fnl) == 0:
        fnl = [i["sell_price_min"] for i in x if i["sell_price_min"] != 0]
    # when there is only one entry point
    if len(fnl) == 1:
        return fnl[0]
    # when everything is 0
    elif len(fnl) == 0:
        return 0
    # Use list comprehension to remove extremes from the list, also use the statistics.mean function to get averages from the data.
    return avg([i for i in fnl if i <= 3 * avg(sorted(fnl)[:-1])])


# determines gear worth
async def calculate_gearworth(person, session):
    # initialise list of inventory and total value
    loi = []
    total = 0
    # unpack user items, get gear
    for position, gear in person["Equipment"].items():
        # Gear is sometimes None if the user did not use the value
        if gear is not None:
            loi.append((gear["Type"], gear['Quality']))
    # looping through items in counter
    for items, count in Counter(loi).items():
        try:
            total += _getaverage(await get_iw_json(items[0], session),
                                 items[1]) * count
        except KeyError:
            logging.info("Time: {0:20} KeyError: Item {1}".format(
                datetime.datetime.now().strftime("%x %X:%f"), items[0]))
    return total


async def drawplayer(player,
                     kav,
                     totaldamage=0,
                     killer=True,
                     peoplegettingfame=0):
    # Base image link to load the images
    _baseimagelink = "https://render.albiononline.com/v1/item/"

    # kav is used to determine if hte player is killer, assist or victim
    # Create a new image
    playerimg = img.new("RGBA", (600, 1200), BACKGROUND)
    # set lambda functions to put text in the middle of width and height
    wmiddle = lambda x: (600 - x) / 2
    hmiddle = lambda x, y, z: x + (y - z) / 2
    # set drawing image for putting text
    drawimg = imgdraw.Draw(playerimg)
    # Get width and height of text
    width, height = drawimg.textsize(kav, font=defaultfont)
    # Set a text for the heading, padding of 10.
    drawimg.text((wmiddle(width), hmiddle(10, 50, height)),
                 text=kav,
                 font=defaultfont,
                 fill=RED)
    # height after this starts from 65.0
    width, height = drawimg.textsize(player["Name"], font=namesfont)
    drawimg.text((wmiddle(width), hmiddle(65, 50, height)),
                 text=player["Name"],
                 font=namesfont,
                 fill=WHITE)
    # After this line of the text will start at height 140
    # Get user guild name as shown in the game
    fullguildname = "{0}{1}".format(player["AllianceName"], player["GuildName"])
    # Get the width and height of the guild name in text
    width, height = drawimg.textsize(fullguildname, font=namesfont_small)
    drawimg.text((wmiddle(width), hmiddle(150, 25, height)),
                 text=fullguildname,
                 font=namesfont_small,
                 fill=BLUE)
    # set a variable for easy access
    equipments = player["Equipment"]
    """
    File structure for data.json:
    [itemname, photolocation, textspace]
    itemname: UNIQUE_NAME key for the using item, can be used as a key to look for the image online from the database
    photolocation: location data on the image, it is a 2 point tuple that helps determine the x and y value of the upper left corner of the photo
    textspace: location data for the count of the item. Usually only useful in potion slot and food slot, used to determine the count of the item.
    """
    async with aiohttp.ClientSession() as session:
        # unpacks the data
        for item, imgspace, textspace in data:
            # check if the item exists
            if equipments[item]:
                # downloads image
                loadingimg = await get_image(_baseimagelink,
                                             equipments[item]["Type"], session,
                                             equipments[item]["Quality"])
                # puts the image on the background using the given data
                playerimg.paste(loadingimg, imgspace)
                # put the count on the pasted image using the given data
                drawimg.text(textspace,
                             text=str(equipments[item]["Count"]),
                             font=systemfont,
                             fill=WHITE)
    # Check if user is using a two-handed weapon
    try:
        twohand = await is_two_main_hand(equipments["MainHand"]["Type"])
    except Exception as e:
        twohand = False

    if twohand and equipments["MainHand"]:
        # downloads the image again from the database
        async with aiohttp.ClientSession() as session:
            content = await get_image(_baseimagelink,
                                      equipments["MainHand"]["Type"], session,
                                      equipments["MainHand"]["Count"])
            content.putalpha(100)
        # make the image transparent
        playerimg.paste(content, (400, 380))
        # provides the count
        drawimg.text((533, 490),
                     text=str(equipments["MainHand"]["Count"]),
                     font=systemfont,
                     fill=WHITE)
    # Calculate their gear worth
    async with aiohttp.ClientSession() as session:
        gearworth = await calculate_gearworth(player, session)
    # Set IP
    width, height = drawimg.textsize("IP: {}".format(
        round(player["AverageItemPower"], 2)),
                                     font=largesystemfont)
    drawimg.text((wmiddle(width), 930),
                 "IP: {}".format(round(player["AverageItemPower"], 2)),
                 font=largesystemfont,
                 fill=WHITE)
    if killer:
        damageline = "Damage done:\n{}%[{}/{}]".format(
            lzfloat(player["DamageDone"] / totaldamage * 100).round_sf(4),
            round(int(player["DamageDone"])), totaldamage)
    else:
        damageline = "Death Fame: {} [{}]\n ={}/particiant".format(
            player["DeathFame"], peoplegettingfame,
            player["DeathFame"] // peoplegettingfame)
    width, height = drawimg.textsize(damageline, font=infotext)
    # Both death fame and the damage done are multiline texts.
    drawimg.multiline_text((wmiddle(width), hmiddle(1000, 70, height)),
                           damageline,
                           font=infotext,
                           fill=WHITE)
    # Convert the gear worth into integer and round the gear worth to 5 signifacant figures
    gearworthline = "Estimated Gear Worth: {:,}".format(
        lzint(gearworth).round_sf(5))
    width, height = drawimg.textsize(gearworthline, font=infotext)
    # Set gear worth
    drawimg.text((wmiddle(width), hmiddle(1120, 40, height)),
                 gearworthline,
                 font=infotext,
                 fill=(RED if gearworth >= 1000000 else WHITE))
    return playerimg


class kill:

    def __init__(self, kd):
        """
        Usage: 
        variable = kill(kill json item)
        """
        self.starttime = timetime()
        kd = dc(kd)
        self.kd = kd
        self.killer = kd["Killer"]
        # Track killer
        for i in kd["Participants"]:
            if i["Id"] == kd["Killer"]["Id"]:
                self.killer = dc(i)
                break
        try:
            if not self.killer["DamageDone"]:
                self.killer["DamageDone"] = 0
        except KeyError:
            self.killer["DamageDone"] = 0
        # track victim
        self.victim = kd["Victim"]
        # Get the people who did the most damage
        try:
            self.assist = sorted(
                [i for i in kd["Participants"] if i["DamageDone"] > 0],
                key=lambda x: x["DamageDone"],
                reverse=True)[0]
        # Happens when the amount of participants is less than 1(even though I don't know how did it happen)
        except IndexError:
            self.assist = dc(self.killer)
        # Set type of solo kill or group kill
        # Is used to show if 3 people is shown on the final kill or 2
        self.solokill = (self.killer["Id"] == self.assist["Id"])
        # Set alliance names to the one similar in game
        if self.killer["AllianceName"]:
            self.killer["AllianceName"] = "[{}]".format(
                self.killer["AllianceName"])
        if self.assist["AllianceName"]:
            self.assist["AllianceName"] = "[{}]".format(
                self.assist["AllianceName"])
        if self.victim["AllianceName"]:
            self.victim["AllianceName"] = "[{}]".format(
                self.victim["AllianceName"])
        # Set victim guild if victim does not have a guild
        if not self.killer["GuildName"]:
            self.killer["GuildName"] = "- - - - -"
        if not self.assist["GuildName"]:
            self.assist["GuildName"] = "- - - - -"
        if not self.victim["GuildName"]:
            self.victim["GuildName"] = "- - - - -"
        self.totaldamage = int(
            sum([i["DamageDone"] for i in kd["Participants"]]))
        self.peoplegettingfame = len(
            [i for i in kd["GroupMembers"] if i["KillFame"] > 0])

        # Get the list of participants that dealt damage
        self.participants = sorted(
            [i for i in kd["Participants"] if i["DamageDone"] != 0],
            key=lambda x: x["DamageDone"],
            reverse=True)
        for i in self.participants:
            if i["AllianceName"] and not match(r"\[.*\]", i["AllianceName"]):
                i["AllianceName"] = "[{}]".format(i["AllianceName"])
        self.eventid = kd["EventId"]
        # Use regex and datetime module to get the time of killing in UTC
        dt = match(
            r"(\d{4})\-(\d{2})\-(\d{2})T(\d{2})\:(\d{2})\:(\d{2}\:*)\.(\d+)Z",
            kd["TimeStamp"])
        self.eventtime = datetime.datetime(int(dt.group(1)), int(dt.group(2)),
                                           int(dt.group(3)), int(dt.group(4)),
                                           int(dt.group(5)), int(dt.group(6)),
                                           int(dt.group(7)[:6]))
        if self.peoplegettingfame == 0:
            self.peoplegettingfame = len(kd["GroupMembers"])
            logging.warning("Peoplegetting fame error: {}".format(self.eventid))
        if self.totaldamage == 0:
            self.totaldamage = 100
            logging.warning("totaldamage error: {}".format(self.eventid))

    # Function to draw a whole set of gear on a blank template
    async def draw(self):
        background = img.new("RGBA", (1800, 1200), BACKGROUND)
        # load pictures for each player
        killer_pic = await drawplayer(self.killer,
                                      "Killer",
                                      totaldamage=self.totaldamage,
                                      killer=True)
        victim_pic = await drawplayer(self.victim,
                                      "Victim",
                                      killer=False,
                                      peoplegettingfame=self.peoplegettingfame)
        if self.solokill:
            background.paste(killer_pic, (150, 0))
            background.paste(victim_pic, (1050, 0))
        else:
            assist_pic = await drawplayer(self.assist,
                                          "Assist",
                                          killer=True,
                                          totaldamage=self.totaldamage)
            background.paste(killer_pic, (0, 0))
            background.paste(assist_pic, (600, 0))
            background.paste(victim_pic, (1200, 0))
        self.fileloc = f"temp/{self.eventid}.png"
        background.save(self.fileloc, "png")
        # returns gear worth
        async with aiohttp.ClientSession() as session:
            self.gw = round(await calculate_gearworth(self.victim, session))
        self.inv = await self.inventory()
        return background

    # returns a tuple of 3 values, [kill/assist] name, guild(allliance) and damage[percentage]
    @property
    def assists(self):
        # list of names for participants
        fn = [i["Name"] for i in self.participants]
        # List of guild naems
        guild = [(i["AllianceName"] +
                  i["GuildName"] if i["GuildName"] else "- - - - -")
                 for i in self.participants]
        # list of damage/percent of total damage
        perc = [
            "{:4}[{}%]".format(
                round(i["DamageDone"]),
                round(i['DamageDone'] / self.totaldamage * 100, 2))
            for i in self.participants
        ]
        # return joins
        return ("\n".join(fn), "\n".join(guild), "\n".join(perc))

    def title(self, iskiller=False, isvictim=False, isassist=False):
        if (iskiller or isassist) and isvictim:
            useitem = prefixes["ffire"]
        elif self.solokill and len(self.participants) == 1 and iskiller:
            useitem = prefixes["solo"]
        elif (iskiller or isassist) and self.victim["DeathFame"] >= 500000:
            useitem = prefixes["juicyk"]
        elif iskiller:
            useitem = prefixes["kill"]
        elif isassist:
            useitem = prefixes["assist"]
        elif isvictim and self.victim["DeathFame"] >= 500000:
            useitem = prefixes["juicyd"]
        elif isvictim:
            useitem = prefixes["death"]
        else:
            useitem = prefixes["juicy"]
        return (
            f"{self.killer['Name']} killed {self.victim['Name']} for {self.victim['DeathFame']} kill fame. :{randchoice(useitem['emoji'])}:",
            f"{randchoice(useitem['choices'])}")

    async def inventory(self):
        stuff = []
        async with aiohttp.ClientSession() as session:
            for i in [j for j in self.victim["Inventory"] if j is not None]:
                itemworth = _getaverage(await get_iw_json(i["Type"], session),
                                        i["Quality"])
                stuff.append(
                    (items_get(i["Type"],
                               i["Quality"]), int(i["Count"]), int(itemworth)))
        for i in stuff:
            self.gw += i[2] * i[1]
        sortedstuff = sorted(stuff, key=lambda x: x[2], reverse=True)
        rs = lambda x, y: "\n".join([str(i[int(x)]) for i in tuple(y)])
        if any(len(rs(0, sortedstuff)) > 1024 for x in range(0, 3)):
            s0, s1 = (lzlist(sortedstuff).split_to(2))
            return (rs(0, s0), rs(1, s0), rs(2, s0), rs(0, s1), rs(1, s1),
                    rs(2, s1), True)
        return (rs(0, sortedstuff), rs(1, sortedstuff), rs(2, sortedstuff), "",
                "", "", False)

    def create_embed(self, followinglists):
        self.file = discordfile(self.fileloc, filename=f"{self.eventid}.png")
        # find kill type
        iskiller = self.killer["Id"] in followinglists or self.killer[
            "GuildId"] in followinglists
        isvictim = self.victim["Id"] in followinglists or self.victim[
            "GuildId"] in followinglists
        isassist = False
        for i in [i for i in self.kd["Participants"] if i["DamageDone"] > 0]:
            if i["Id"] in followinglists or i["GuildId"] in followinglists:
                isassist = True
        if (iskiller or isassist) and isvictim:
            color = 0xae00ff
        elif (iskiller or isassist):
            color = 0x00ff00
        elif isvictim:
            color = 0xff0000
        else:
            color = 0x00ffff
        localtitle, localdescription = self.title(iskiller, isvictim, isassist)
        # Create discord embed object
        self.embed = None
        self.embed = discordembed(
            title=localtitle,
            url=f"https://albiononline.com/en/killboard/kill/{self.eventid}",
            description=localdescription + "!" * rrange(1, 3),
            color=color,
            timestamp=self.eventtime)
        # derives image link from eventid as uploads are done in draw() function
        self.embed.set_image(url=f"attachment://{self.eventid}.png")
        self.embed.set_footer(text="Local Kill time: ")
        # get an assist list
        self.assistlist = self.assists
        # This step may encounter an error where no one dealt damage
        # These two lines fixes the output and prevent httperror where value is None
        if self.assistlist == ("", "", ""):
            # Forcibly set assistlist to a tuple
            self.assistlist = (self.killer["Name"], self.killer["GuildName"],
                               "100[100%]")
        # Add in values for the embed
        self.embed.add_field(name="Killers", value=self.assistlist[0])
        self.embed.add_field(name="Guild",
                             value=self.assistlist[1],
                             inline=True)
        self.embed.add_field(name="Damage",
                             value=self.assistlist[2],
                             inline=True)
        # check if victim's inventory is empty
        if len([i for i in self.victim["Inventory"] if i is not None]) > 0:
            i0, c0, v0, i1, c1, v1, lis2 = self.inv
            # adds embed field for victim's inventory
            self.embed.add_field(name="Victim's Inventory:",
                                 value=i0,
                                 inline=True)
            self.embed.add_field(name="Amount", value=c0, inline=True)
            self.embed.add_field(name="Worth est.", value=v0, inline=True)
            if lis2:
                self.embed.add_field(name="Inventory", value=i1, inline=True)
                self.embed.add_field(name="Amount", value=c1, inline=True)
                self.embed.add_field(name="Worth est.", value=v1, inline=True)

        # adds embed field for the total gear worth.
        self.embed.add_field(name="Estimated Victim's Total Worth:",
                             value="{:,}".format(self.gw),
                             inline=False)
        '''
        returns three items: 
        self.embed: the embed file to be sent
        self.file: the file object that has to be sent together with the embed 
        self.fileloc: the file location that would later delete the original file.
        '''
        return (self.embed, self.file, self.fileloc)
