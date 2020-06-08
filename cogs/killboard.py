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

    async def start(self):
        # set a old example for comparison
        # Defauit value is 0 as we want to get the latest information
        self.old = await self._connect(0)
        # initialise the new variable
        self.new = dc(self.old)
        self.set = True
        print("objcreated")
        return

    # Get a connection and download value from the gameinfo api
    @staticmethod
    async def _connect(offset):

        # function that returns the proper link via string formatting
        _link = lambda x: "https://gameinfo.albiononline.com/api/gameinfo/events?limit=51&offset={}".format(
            x)

        # using the requests module to get a connection from the link
        # offset can be adjusted if more than 51 kills occured between updates
        async with aiohttp.ClientSession() as client:
            async with client.get(_link(offset)) as resp:
                if resp.status != 200:
                    await asyncio.sleep(1)
                    print(resp.status)
                    logging.warning(
                        "Time: {0:20} Status Code Error: {1}".format(
                            datetime.datetime.now().strftime("%x %X:%f"),
                            resp.status))
                    return await killboard._connect(offset)
                return await resp.json()

    @property
    def compare(self):
        return self.new == self.old

    @property
    def new_values(self):
        return [i for i in self.new if i not in self.old]

    async def load(self):
        print("loaddinggg..")
        # Get the new values of new
        self.new = await self._connect(0)
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
        # Make a copy to later replace the old value
        temp = dc(self.new)
        # determines if 1 query is enough for all the new kills
        # also, the api does not allow query >= 1000
        while (len(self.diff) >=
               (51 * (count + 1))) and (51 * count + 1 < 1000):
            count += 1
            await asyncio.sleep(1)
            print("new connections made")
            # load api with added offset
            self.new = await self._connect(51 * count)
            # compare and load new vaules
            self.diff += self.new_values
            # append to old for unique values
            self.old += self.new
            continue
        # Set old to the latest kills
        print("All differences found")
        self.old = dc(temp)
        print("Total: {}".format(len(self.diff)))
        return self.diff

    @staticmethod
    async def search(tpe, name):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        "https://gameinfo.albiononline.com/api/gameinfo/search?q="
                        + "+".join([i for i in name])) as resp:
                    # Prevent the TypeError: 'coroutine' object is not subscriptable
                    m = await resp.json()
                    try:
                        m = m[tpe][0]
                        return ("Now following: {} {} [{}]".format(
                            tpe, m["Name"], m["Id"]), m["Id"], m["Name"], True)
                    except IndexError:
                        return ("{} cannot be found in the database!".format(
                            " ".join([i for i in name])), None, None, False)
        except aiohttp.client_exceptions.ContentTypeError:
            logging.warning("aiohttp.client_exceptions.ContentTypeError")
            await asyncio.sleep(2)
            return await killboard.search(tpe, name)

    # Determines if one kill should be converted into images
    #
    def insearch(self, kill):
        return any([
            kill["Killer"]["Id"] in self.tracking, kill["Killer"]["GuildId"] in
            self.tracking, kill["Victim"]["Id"] in self.tracking, kill["Victim"]
            ["GuildId"] in self.tracking
        ] + [kill["TotalVictimKillFame"] >= self.minkillfame])

    async def newkills(self):
        return [i for i in await self.load() if self.insearch(i)]

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
            kill["TotalVictimKillFame"] >= guild["minimumkillfame"]
        ])
