import asyncio
import datetime
import logging
from copy import deepcopy as dc

import aiohttp


class killboard:

    def __init__(self):
        # initialise a set variable to make sure if it is online
        self.set = False
        # initalise the differnce variable
        self.diff = []
        # initialise tracking guilds/alliances
        self.tracking = []
        # variable minkillfame that determines a large kill to be displayed
        self.minkillfame = 10000
        #set false value
        self.ready = False

    async def start(self):
        # set a old example for comparison
        # Defauit value is 0 as we want to get the latest information
        async with aiohttp.ClientSession() as client:
            self.old = await self._connect(0, client)
        # initialise the new variable
        self.new = dc(self.old)
        self.set = True
        print("objcreated")
        return

    # Get a connection and download value from the gameinfo api
    @staticmethod
    async def _connect(offset, client=None, count=0):

        # function that returns the proper link via string formatting
        _link = lambda x: "https://gameinfo.albiononline.com/api/gameinfo/events?limit=51&offset={}".format(
            x)

        # using the requests module to get a connection from the link
        # offset can be adjusted if more than 51 kills occured between updates
        async with client.get(_link(offset)) as resp:
            if resp.status != 200:
                await asyncio.sleep(count + 1)
                logging.warning("Time: {0:20} Status Code Error: {1}".format(
                    datetime.datetime.now().strftime("%x %X:%f"), resp.status))
                return await killboard._connect(offset, client, count + 1)
            return await resp.json()

    @property
    def compare(self):
        return self.new == self.old

    @property
    def new_values(self):
        return [i for i in self.new if i not in self.old]

    async def load(self):
        async with aiohttp.ClientSession() as client:
            # Get the new values of new
            self.new = await self._connect(0, client)
        # returns none if nothing new is updated on the api
        if self.compare:
            print("nothing new")
            return []
        print("NEW ITEMSS!!!")
        # initialise the count variable for later offsets
        count = 0
        self.diff = self.new_values
        """
        to avoid repetition in the future
        Both self.old and self.new are lists(json data from the website)
        """
        self.old += self.new
        # determines if 1 query is enough for all the new kills
        # also, the api does not allow query >= 1000
        async with aiohttp.ClientSession() as client:
            while True:
                try:
                    count += 1
                    self.new = await self._connect(50 * count, client)
                    self.new.sort(key=lambda x: int(x["EventId"]))
                    self.diff += [
                        i for i in self.new_values if i not in self.diff
                    ]
                    self.old += self.new
                    self.old.sort(key=lambda x: int(x["EventId"]))
                    if (50 * count + 1) > 1000:
                        break
                    elif len(self.diff) < (30 * count):
                        break
                except Exception as e:
                    print(type(e), e.message)
        # Set old to the latest kills
        print("Total: {}".format(len(self.diff)))
        if len(self.old) >= 2000:
            self.old = self.old[len(self.old) - 2000::1]
        if not self.ready:
            self.ready = True
            return []
        return sorted(self.diff, key=lambda x: int(x["EventId"]))

    @staticmethod
    async def search(tpe, name):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        "https://gameinfo.albiononline.com/api/gameinfo/search?q="
                        + "+".join([i for i in name])) as resp:
                    # json function is a coroutine
                    m = await resp.json()
                    try:
                        # default gets the first result as a return
                        m = m[tpe][0]
                        # send message is returned, ID is used to trace the kill
                        return ("Now following: {} {} [{}]".format(
                            tpe, m["Name"], m["Id"]), m["Id"], m["Name"], True)
                    except IndexError:
                        return ("{} cannot be found in the database!".format(
                            " ".join([i for i in name])), None, None, False)
        except aiohttp.client_exceptions.ContentTypeError:
            logging.warning("aiohttp.client_exceptions.ContentTypeError")
            await asyncio.sleep(2)
            return await killboard.search(tpe, name)

    def isassist(self, kill):
        for parts in kill["Participants"]:
            if parts["Id"] in self.tracking or parts["GuildId"] in self.tracking:
                return True

    # Determines if one kill should be converted into images
    def insearch(self, kill):
        return any([
            kill["Killer"]["Id"] in self.tracking, kill["Killer"]["GuildId"] in
            self.tracking, kill["Victim"]["Id"] in self.tracking, kill["Victim"]
            ["GuildId"] in self.tracking
        ] + [kill["TotalVictimKillFame"] >= self.minkillfame] +
                   [self.isassist(kill)])

    async def newkills(self):
        return [i for i in await self.load() if self.insearch(i)]

    @staticmethod
    def inguildassist(kill, guild):
        for parts in kill["Participants"]:
            if parts["Id"] in guild["trackingplayer"]:
                return True
            if parts["GuildId"] in guild["trackingguild"]:
                return True
        return False

    # static method to check if a kill should be sent in one channel
    # parameters: guild[guild object], kill[kill object]
    @staticmethod
    def qualify(guild, kill):
        return any([
            # tracking player is the killer
            kill["Killer"]["Id"] in guild["trackingplayer"],
            # tracking player is the victim
            kill["Victim"]["Id"] in guild["trackingplayer"],
            # killer's guild is in the list of tracking guilds
            kill["Killer"]["GuildId"] in guild["trackingguild"],
            # victim's guild is in list of tracking guilds
            kill["Victim"]["GuildId"] in guild["trackingguild"],
            # the total kill fame is larger than the lowest set kill fame in the guild
            kill["TotalVictimKillFame"] >= guild["minimumkillfame"],
            killboard.inguildassist(kill, guild)
        ])
