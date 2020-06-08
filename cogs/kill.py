import datetime
import json
import logging
import os
import time
from collections import Counter
from copy import deepcopy as dc
from io import BytesIO
from re import match
from statistics import mean as avg

import aiohttp
import requests
from bs4 import BeautifulSoup as bs
from lzl import lzfloat, lzint, lzlist
from PIL import Image as img
from PIL import ImageDraw as imgdraw
from PIL import ImageFont as imgfont

import discord

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
del requests


# Return item name from given unique key
def items_get(items):
    try:
        return [
            i["LocalizedNames"]["EN-US"]
            for i in formatteditems
            if i["UniqueName"] == items
        ][0]
    except:
        return items


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
async def get_image(link, session):
    async with session.get(link) as resp:
        # use bytesio object to load the respond conetent from online∂
        # -> use image module to load the image from bytesio object
        # -> resize the image object to 180x180 size
        # -> convert the image to transparent
        return convert_to_transparent(
            img.open(BytesIO(await resp.content.read())).resize(
                (180, 180), img.ANTIALIAS), BACKGROUND)


# determines gear worth
async def calculate_gearworth(person, onlygear=False):

    # Function to get the average price from Lymhurst, Martlock, Bridgewatch, FortSterling and Thetford
    def _getaverage(x, y):
        fnl = []
        for i in x:
            if i['quality'] == y:
                fnl.append(i["sell_price_min"])
        if len(fnl) != 5:
            fnl = [i["sell_price_min"] for i in x if i["quality"] == 1]
        # Use list comprehension to remove extremes from the list, also use the statistics.mean function to get averages from the data.
        return avg([i for i in fnl if i <= 3 * avg(sorted(fnl)[:-1])])

    # Lambda function to return the api link
    getlink = lambda x: "https://www.albion-online-data.com/api/v2/stats/prices/" + x + "?locations=Lymhurst,Martlock,Bridgewatch,FortSterling,Thetford"
    # initialise list of inventory and total value
    loi = []
    total = 0
    # unpack user items, get gear
    for position, gear in person["Equipment"].items():
        # Gear is sometimes None if the user did not use the value
        if gear is not None:
            loi.append((gear["Type"], gear['Quality']))
    if not onlygear:
        # loop through items in victims inventory
        for items in person["Inventory"]:
            # even if there is nothing in the inventory, it would be an array of none objects
            if items is None:
                continue
            # Count would also count into the
            for count in range(items["Count"]):
                loi.append((items["Type"], items["Quality"]))
    # looping through items in counter
    for items, count in Counter(loi).items():
        async with aiohttp.ClientSession() as session:
            async with session.get(getlink(items[0])) as resp:
                valueslist = await resp.json()
        try:
            total += _getaverage(valueslist, items[1]) * count
        except KeyError:
            logging.info("Time: {0:20} KeyError: Item {1}".format(
                datetime.datetime.now().strftime("%x %X:%f"), items[0]))
            continue
    return total


async def drawplayer(player,
                     kav,
                     totaldamage=0,
                     killer=True,
                     peoplegettingfame=0):
    # Base image link to load the images
    _baseimagelink = "https://gameinfo.albiononline.com/api/gameinfo/items/"

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

    # get accurate plotting locations and names.
    try:
        with open("data.json") as file:
            data = json.load(file)
    except FileNotFoundError:
        with open("cogs/data.json") as file:
            data = json.load(file)
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
                loadingimg = await get_image(
                    _baseimagelink + equipments[item]["Type"], session)
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
            async with session.get(_baseimagelink +
                                   equipments["MainHand"]["Type"]) as resp:
                content = img.open(BytesIO(await resp.content.read())).resize(
                    (180, 180), img.ANTIALIAS)
                content = convert_to_transparent(content, BACKGROUND)
                content.putalpha(100)
        # make the image transparent
        playerimg.paste(content, (400, 380))
        # provides the count
        drawimg.text((533, 490),
                     text=str(equipments["MainHand"]["Count"]),
                     font=systemfont,
                     fill=WHITE)
    # Calculate their gear worth
    gearworth = await calculate_gearworth(player, True)
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
            lzfloat(player["DamageDone"] / totaldamage * 100).round_sf(3),
            player["DamageDone"], totaldamage)
    else:
        damageline = "Death Fame: {}[{}]\n ={}/particiant".format(
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
        kd = dc(kd)
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
            self.assist = sorted([i for i in kd["Participants"]],
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
        self.participants = [
            i for i in kd["Participants"] if i["DamageDone"] != 0
        ]
        for i in self.participants:
            if i["AllianceName"] and not match(r"\[.*\]", i["AllianceName"]):
                i["AllianceName"] = "[{}]".format(i["AllianceName"])
        self.eventid = kd["EventId"]
        # Use regex and datetime module to get the time of killing in UTC
        dt = match(
            r"(\d{4})\-(\d{2})\-(\d{2})T(\d{2})\:(\d{2})\:(\d{2}\:*)\.(\d+)Z",
            kd["TimeStamp"])
        self.eventtime = datetime.datetime(
            int(dt.group(1)), int(dt.group(2)), int(dt.group(3)),
            int(dt.group(4)), int(dt.group(5)), int(dt.group(6)),
            int(dt.group(7)[:6])).strftime("%d %B %Y, %H:%M:%d:%f UTC")
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
        print("Killerpic")
        killer_pic = await drawplayer(self.killer,
                                      "Killer",
                                      totaldamage=self.totaldamage,
                                      killer=True)
        print("Victimpic")
        victim_pic = await drawplayer(self.victim,
                                      "Victim",
                                      killer=False,
                                      peoplegettingfame=self.peoplegettingfame)
        if self.solokill:
            background.paste(killer_pic, (150, 0))
            background.paste(victim_pic, (1050, 0))
        else:
            print("Assistpic")
            assist_pic = await drawplayer(self.assist,
                                          "Assist",
                                          killer=True,
                                          totaldamage=self.totaldamage)
            background.paste(killer_pic, (0, 0))
            background.paste(assist_pic, (600, 0))
            background.paste(victim_pic, (1200, 0))
        self.fileloc = f"temp/{self.eventid}.png"
        background.save(self.fileloc, "png")
        self.file = discord.File(self.fileloc, filename=f"{self.eventid}.png")
        print("Done")
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
            "{}[{}%]".format(i["DamageDone"],
                             round(i['DamageDone'] / self.totaldamage * 100, 2))
            for i in self.participants
        ]
        # return joins
        return ("\n".join(fn), "\n".join(guild), "\n".join(perc))

    @property
    def victiminv(self):
        # returns victim inventory
        return "\n".join((items_get(i["Type"])
                          for i in self.victim["Inventory"]
                          if i is not None))

    async def embed(self):
        await self.draw()
        # Create discord embed object
        self.embed = discord.Embed(
            title=
            f'{self.killer["Name"]} killed {self.victim["Name"]} for {self.victim["DeathFame"]} kill fame!',
            url=f"https://albiononline.com/en/killboard/kill/{self.eventid}",
            description=f"Time {self.eventtime}")
        # derives image link from eventid as uploads are done in draw() function
        self.embed.set_image(url=f"attachment://{self.eventid}.png")
        # get an assist list
        self.assistlist = self.assists
        # This step may encounter an error where no one dealt damage
        # These two lines fixes the output and prevent httperror where value is None
        if self.assistlist == ("", "", ""):
            # Forcibly set assistlist to a tuple
            self.assistlist = (self.killer["Name"], self.killer["GuildName"],
                               "100[100%")
        # Add in values for the embed
        self.embed.add_field(name="Killers", value=self.assistlist[0])
        self.embed.add_field(name="Guild",
                             value=self.assistlist[1],
                             inline=True)
        self.embed.add_field(name="Damage",
                             value=self.assistlist[2],
                             inline=True)
        # check if victim's inventory is empty
        if self.victiminv != "":
            # adds embed field for victim's inventory
            self.embed.add_field(name="Amount",
                                 value="\n".join(
                                     (str(i["Count"])
                                      for i in self.victim["Inventory"]
                                      if i is not None)),
                                 inline=True)
            self.embed.add_field(name="Victim's Inventory:",
                                 value=self.victiminv,
                                 inline=True)
        # returns gear worth
        gw = str(round(await calculate_gearworth(self.victim)))
        # adds embed field for the total gear worth.
        self.embed.add_field(name="Estimated Victim's Total Worth:",
                             value=gw,
                             inline=False)
        '''
        returns three items: 
        self.embed: the embed file to be sent
        self.file: the file object that has to be sent together with the embed 
        self.fileloc: the file location that would later delete the original file.
        '''
        return (self.embed, self.file, self.fileloc)

    def reload(self):
        # reload is run everytime after one file is sent as discord.File item can only be iterated once
        self.file = discord.File(self.fileloc, filename=f"{self.eventid}.png")
        return (self.embed, self.file, self.fileloc)
