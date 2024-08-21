import os
from time import sleep

import requests
import disnake
from disnake.ext import commands
from disnake.ui import Button, View
from choices_list import *
from google_sheets_manager_v2 import GoogleSheetsManager
from modals.registration_modal import RegistrationModalOne, messages_cache, clear_messages

TOKEN = os.getenv("DISCORD_TOKEN")
googleSheetsManager = GoogleSheetsManager(os.getenv("SHEET_ID"))

# tournament_participants_service = tournament_participants_service.TournamentParticipantsService()
#
# my_thread = threading.Thread(target=tournament_participants_service.run)
#
# my_thread.start()

intents = disnake.Intents.default()
intents.message_content = True

user_cache = {}

bot = commands.InteractionBot(intents=intents, test_guilds=[1251650828519870532])


@bot.event
async def on_ready():
    print("The bot is ready!")


@bot.slash_command(
    name="ping",
    description="Responds with 'Pong!'"
)
async def ping(inter: disnake.ApplicationCommandInteraction):
    await inter.response.send_message("Pong!")


@commands.default_member_permissions(manage_guild=True)
@bot.slash_command(
    name="create",
    description="Create a new tournament"
)
async def create(
        inter: disnake.ApplicationCommandInteraction,
        name: str,
        tournament: str,
        date: str,
        game: str = commands.Param(choices=GAMES),
        form: str = commands.Param(choices=FORMAT)):
    """
      Create a new game tournament.

      Parameters
      ----------
      name: The name of the tournament channel.
      tournament: Tournament ID from challonge
      date: The start time of the tournament
      game: The game to be played.
      form: The format of the game session.

    """

    guild = inter.guild
    existing_channel = disnake.utils.get(guild.channels, name=name)
    category = inter.channel.category

    if existing_channel:
        await inter.response.send_message(f"A channel with the name '{name}' already exists.", ephemeral=True)
    else:
        username = os.getenv("CHALLONGE_LOGIN")
        password = os.getenv("CHALLONGE_API_KEY")
        headers = {'User-Agent': 'Chrome'}

        response = requests.get(f"https://api.challonge.com/v1/tournaments/{tournament}.json",
                                auth=(username, password), headers=headers).json()
        tournament_name = response["tournament"]["name"]

        new_channel = await guild.create_text_channel(name=name, category=category)
        await inter.response.send_message(f"Channel '{new_channel.name}' created successfully!", ephemeral=True)

        register_button = Button(label="Confirm", style=disnake.ButtonStyle.green,
                                 custom_id=f"registration_button:{name}:{tournament}:{game}:{form}")

        cancel_button = Button(label="Cancel", style=disnake.ButtonStyle.red,
                               custom_id=f"cancel_button:{tournament}")

        view = View()
        view.add_item(register_button)
        view.add_item(cancel_button)

        embed = disnake.Embed(
            description=f'Welcome to the **True Gamers server**! This is to confirm your participation in the '
                        f'**{tournament_name}** tournament that will be held on **{date}**.',
            color=7339915
        )

        embed.set_footer(text='To confirm your participation, click on the "Confirm" button and fill out the form. '
                              'We will be waiting for you at our computer club branches.')
        await new_channel.set_permissions(guild.default_role, send_messages=False)

        await new_channel.send(view=view, embed=embed)


@bot.event
async def on_interaction(inter):
    if isinstance(inter, disnake.MessageInteraction):
        custom_id = inter.data.custom_id
        parts = custom_id.split(":")
        if parts[0] == "registration_button":
            name, tournament, game, form = parts[1:]
            data = {
                "tournament_name": name,
                "game": game,
                "form": form,
                "tournament": tournament
            }
            modal = RegistrationModalOne(title="Registration from tournament",
                                         custom_id="registration_modal", data=data,
                                         googleSheetsManager=googleSheetsManager)
            await inter.response.send_modal(modal)
        elif parts[0] == "cancel_button":
            await inter.response.defer()

            await googleSheetsManager.set_deleted_from_tournament(inter.user.name, parts[1])
            await clear_messages(inter)

            channel_name = inter.channel.name

            if messages_cache.get(channel_name) is not None:
                del messages_cache[channel_name]

            embed = disnake.Embed(title="List of participants:", color=7339915)

            users_list = googleSheetsManager.get_item_by_field(parts[1])

            participants = ""

            for user in users_list:
                if user[9] != "DELETED":
                    participants += f"{user[0]}\n"

            embed.description = participants

            await inter.followup.send(embed=embed)

            await inter.followup.send("Participation in the tournament has been canceled", ephemeral=True)


async def get_category(ctx):
    channel = ctx.channel
    if channel.category:
        return channel.category.name
    return False


bot.run(TOKEN)
