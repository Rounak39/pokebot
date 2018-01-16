from bot_logger import logger
from collections import defaultdict
from discord.ext import commands
from math import ceil
from pokeball import POKEBALL_LIST
from legendary import LEGENDARY_PKMN, ULTRA_PKMN
import discord
import glob
import json
import os
import random
import re
import time


class PokemonCommands:
    """Handles Pokemon related commands"""

    def __init__(self, bot):
        self.cmd_function = PokemonFunctionality(bot)

    @commands.command(name='reload', hidden=True)
    async def reload(self):
        """
        Reloads pokemon data
        """
        await self.cmd_function.reload_data()

    @commands.command(name='pokemon', pass_context=True)
    async def pokemon(self, ctx):
        """
        Catches a random pokemon

        @param ctx - context of the command sent
        """
        await self.cmd_function.catch_pokemon(ctx)

    @commands.command(name='inventory', pass_context=True)
    async def pinventory(self, ctx, page_number=1):
        """
        Displays the trainer's pokemon inventory

        @param ctx - context of the command sent
        """
        await self.cmd_function.display_pinventory(ctx, page_number)


class PokemonFunctionality:
    """Handles Pokemon Command Functionality"""

    def __init__(self, bot):
        self.bot = bot
        self.nrml_pokemon = self._load_pokemon_imgs()
        self.trainer_data = self._check_trainer_file()
        self._save_trainer_file(self.trainer_data, backup=True)

    def _check_trainer_file(self):
        """
        Checks to see if there's a valid trainers.json file
        """
        try:
            with open('trainers.json') as trainers:
                return json.load(trainers)
        except FileNotFoundError:
            self._save_trainer_file()
            return json.loads('{}')
        except Exception as e:
            print("An error has occured. See error.log.")
            logger.error("Exception: {}".format(str(e)))

    def _save_trainer_file(self, trainer_data={}, backup=False):
        """
        Saves trainers.json file
        """
        if backup:
            trainer_filename = "trainers_backup.json"
        else:
            trainer_filename = "trainers.json"
        with open(trainer_filename, 'w') as outfile:
            json.dump(trainer_data,
                      outfile,
                      indent=4)

    def _load_pokemon_imgs(self):
        """
        Loads pokemon images within a folder

        Note: Make path universal
        """
        filedict = defaultdict(list)
        folder_path = os.path.join('assets', 'nrml')
        img_path = os.path.join('assets', 'nrml', '*.png')
        for filename in glob.glob(img_path):
            result = re.match(r'([^\d]+)', filename)
            if result:
                pkmn_name = filename
                pkmn_name = pkmn_name.replace(folder_path, "")
                pkmn_name = pkmn_name.replace('/', "")
                pkmn_name = pkmn_name.replace('\\', "")
                pkmn_name = pkmn_name.replace('.png', "")
                filedict[pkmn_name].append(filename)
        return filedict

    async def reload_data(self):
        """
        Reloads cog manager
        """
        try:
            self.nrml_pokemon = self._load_pokemon_imgs()
            self.trainer_data = self._check_trainer_file()
            await self.bot.say("Reload complete.")
        except Exception as e:
            error_msg = 'Failed to reload: {}'.format(str(e))
            print(error_msg)
            logger.error(error_msg)

    async def display_pinventory(self, ctx, page_number):
        """
        Displays pokemon inventory
        """
        try:
            user = ctx.message.author.name
            user_id = ctx.message.author.id
            pinventory = self.trainer_data[user_id]["pinventory"]
            pinventory_count = 0
            msg = ''
            i = (page_number-1)*20
            for pkmn in pinventory.items():
                if i >= 20*page_number:
                    break
                msg += "{} x{}\n".format(pkmn[0].title(), pkmn[1])
                pinventory_count += int(pkmn[1])
                i += 1
            max_pages = ceil(pinventory_count/20)
            msg = ("__**{}'s Pokemon**__: Includes **{}** Pokemon. "
                   "[Page **{}/{}**]\n"
                   "".format(user, pinventory_count, page_number, max_pages)
                   + msg)
            try:
                await self.bot.say(msg)
            except:
                pass
        except Exception as e:
            print("An error has occured in displaying inventory. "
                  "See error.log.")
            logger.error("Exception: {}".format(str(e)))

    async def _check_cooldown(self, ctx, current_time):
        """
        Checks if cooldown has passed
        True if cooldown is still active
        False if cooldown is not active
        """
        user = ctx.message.author.name
        user_id = ctx.message.author.id
        timer = float(self.trainer_data[user_id]["timer"])
        cooldown_time = time.time() - timer
        hours = int(cooldown_time // 3600)
        minutes = int((cooldown_time % 3600) // 60)
        seconds = int(cooldown_time % 60)
        if minutes >= 10 or hours >= 1:
            return False
        else:
            msg = ":no_entry_sign:**{}**, you need to wait another ".format(user)
            msg += "**{} minutes &** ".format(str(9-minutes))
            msg += "**{} seconds** ".format(str(60-seconds))
            msg += "before catching another pokemon."
            await self.bot.say(msg)
            return True

    async def _post_pokemon_catch(self, ctx, user, random_pkmn, pkmn_img_path, random_pkmnball):
        """
        Posts the pokemon that was caught
        """
        try:
            ctx_channel = ctx.message.channel
            msg = ("{}, {} you've caught a "
                   "**{}**!".format(user,
                                    random_pkmnball,
                                    random_pkmn.replace('_', ' ').title()))
            if random_pkmn in LEGENDARY_PKMN or random_pkmn in ULTRA_PKMN:
                for channel in ctx.message.server.channels:
                    if "legendary" in channel.name:
                        legendary_channel = self.bot.get_channel(channel.id)
                        break
                em = discord.Embed(description=msg,
                                   colour=0xFFFFFF)
                em.set_thumbnail(url="https://raw.githubusercontent.com/msikma/"
                                     "pokesprite/master/icons/pokemon/regular/"
                                     "{}.png"
                                     "".format(random_pkmn.replace('_', '-')))
                em.set_image(url="https://play.pokemonshowdown.com/sprites/"
                                 "xyani/{}.gif"
                                 "".format(random_pkmn.replace('_', '')))
                await self.bot.send_message(legendary_channel,
                                            embed=em)
            await self.bot.send_file(destination=ctx_channel,
                                     fp=pkmn_img_path,
                                     content=msg)
        except:
            pass

    async def catch_pokemon(self, ctx):
        """
        Generates a random pokemon to be caught
        """
        try:
            current_time = time.time()
            user_id = ctx.message.author.id
            if user_id not in self.trainer_data:
                self.trainer_data[user_id] = {}
                self.trainer_data[user_id]["pinventory"] = {}
                self.trainer_data[user_id]["timer"] = False
            if not await self._check_cooldown(ctx, current_time):
                # random_pkmn = random.choice(list(self.nrml_pokemon.keys()))
                random_pkmn = "tapu_koko"
                random_pkmnball = random.choice(list(POKEBALL_LIST))
                pkmn_img_path = self.nrml_pokemon[random_pkmn][0]
                user = "**{}**".format(ctx.message.author.name)
                trainer_profile = self.trainer_data[user_id]
                # trainer_profile["timer"] = current_time
                trainer_profile["timer"] = 0
                if random_pkmn not in trainer_profile["pinventory"]:
                    trainer_profile["pinventory"][random_pkmn] = 1
                else:
                    pokemon_count = int(trainer_profile["pinventory"][random_pkmn])
                    trainer_profile["pinventory"][random_pkmn] = pokemon_count+1
                self._save_trainer_file(self.trainer_data)
                await self._post_pokemon_catch(ctx,
                                               user,
                                               random_pkmn,
                                               pkmn_img_path,
                                               random_pkmnball)
        except Exception as e:
            print("An error has occured in catching pokemon. See error.log.")
            logger.error("Exception: {}".format(str(e)))
