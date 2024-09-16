import asyncio
import json
import os
from datetime import datetime, timedelta

import requests
import disnake
from disnake import PermissionOverwrite
from disnake.ext import commands
from disnake.ui import Button, View
from choices_list import *
from google_sheets_manager_v2 import GoogleSheetsManager
from modals.registration_modal import RegistrationModalOne, messages_cache, clear_messages

TOKEN = os.getenv("DISCORD_TOKEN")
googleSheetsManager = GoogleSheetsManager(os.getenv("SHEET_ID"))

intents = disnake.Intents.default()
intents.message_content = True

# guild_id = 1159429797835976776
guild_id = 1251650828519870532
bot = commands.InteractionBot(intents=intents, test_guilds=[guild_id])


@bot.event
async def on_ready():
    print("The bot is ready!")
    loop = asyncio.get_event_loop()
    loop.create_task(schedule_remove_old_roles())


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
        prefix: str,
        tournament: str,
        date: str,
        game: str = commands.Param(choices=GAMES),
        form: str = commands.Param(choices=FORMAT)):
    """
      Create a new game tournament.

      Parameters
      ----------
      prefix: The name of the tournament channel.
      tournament: Tournament ID from challonge
      date: The start time of the tournament
      game: The game to be played.
      form: The format of the game session.

    """

    guild = inter.guild

    tournament_channel = prefix + "-tournament"
    confirmation_channel = prefix + "-confirmation"

    existing_channel = disnake.utils.get(guild.channels, name=tournament_channel)
    category = inter.channel.category

    if existing_channel:
        await inter.response.send_message(f"A channel with the name '{tournament_channel}' already exists.",
                                          ephemeral=True)
    else:
        username = os.getenv("CHALLONGE_LOGIN")
        password = os.getenv("CHALLONGE_API_KEY")
        headers = {'User-Agent': 'Chrome'}

        response = requests.get(f"https://api.challonge.com/v1/tournaments/{tournament}.json",
                                auth=(username, password), headers=headers).json()
        tournament_name = response["tournament"]["name"]

        new_confirmation_channel = await guild.create_text_channel(name=confirmation_channel, category=category)

        await inter.response.send_message(f"Channel '{new_confirmation_channel.name}' created successfully!",
                                          ephemeral=True)

        new_role = await guild.create_role(name=tournament_channel)

        overwrites = {
            guild.default_role: PermissionOverwrite(read_messages=False),
            new_role: PermissionOverwrite(read_messages=True)
        }

        new_tournament_channel = await guild.create_text_channel(name=tournament_channel, category=category)
        await new_tournament_channel.edit(sync_permissions=True, overwrites=overwrites)

        add_role_to_json(new_role, new_confirmation_channel.id, new_tournament_channel.id)

        register_button = Button(label="Confirm", style=disnake.ButtonStyle.green,
                                 custom_id=f"registration_button:{tournament_channel}:{tournament}:{game}:{form}")

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
        await new_confirmation_channel.edit(sync_permissions=True)
        await new_confirmation_channel.set_permissions(guild.default_role, send_messages=False)

        await new_confirmation_channel.send(view=view, embed=embed)

        embed = disnake.Embed(
            title='Hello, True Gamer!',
            description=f'There is a conversation about the tournament that will take place {prefix}.',
            color=7339915
        )

        await new_tournament_channel.send(embed=embed)


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

            role = disnake.utils.get(inter.guild.roles, name=parts[1])
            tournament = parts[1]

            if role:
                await inter.user.remove_roles(role)

            await googleSheetsManager.set_deleted_from_tournament(inter.user.name, tournament)
            await clear_messages(inter)

            channel_name = inter.channel.name

            if messages_cache.get(channel_name) is not None:
                del messages_cache[channel_name]

            embed = disnake.Embed(title="List of participants:", color=7339915)

            users_list = googleSheetsManager.get_item_by_field(tournament)

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


def add_role_to_json(role, confirmation_id, tournament_id):
    roles_data = {}
    try:
        with open("roles.json", "r") as file:
            roles_data = json.load(file)
    except FileNotFoundError:
        roles_data = {}

    roles_data[str(role.id)] = {"role_name": f"{role.name}",
                                "creation_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "confirmation_channel_id": f"{confirmation_id}",
                                "tournament_channel_id": f"{tournament_id}"}

    with open("roles.json", "w") as file:
        json.dump(roles_data, file)


async def remove_old_roles():
    current_time = datetime.now()
    one_week_ago = current_time - timedelta(days=7)

    try:
        with open("roles.json", "r") as file:
            roles_data = json.load(file)
    except FileNotFoundError:
        return

    removed_count = 0
    for role_id, role_info in list(roles_data.items()):
        if datetime.fromisoformat(role_info["creation_date"]) < one_week_ago:
            try:
                guild = next((g for g in bot.guilds if int(g.id) == int(guild_id)), None)
                if guild:
                    role = guild.get_role(int(role_id))
                    confirmation_channel = guild.get_channel(int(role_info["confirmation_channel_id"]))
                    tournament_channel = guild.get_channel(int(role_info["tournament_channel_id"]))

                    await confirmation_channel.delete()
                    await tournament_channel.delete()

                    if role:
                        await role.delete()
                        del roles_data[role_id]
                        removed_count += 1
                        print(f"Роль '{role_info['role_name']}' удалена из сервера {guild.name}")
            except Exception as e:
                print(f"Ошибка при удалении роли {role_info['role_name']}: {e}")

    if removed_count > 0:
        with open("roles.json", "w") as file:
            json.dump(roles_data, file)
        print(f"Удалено {removed_count} старых ролей.")
    else:
        print("Нет ролей для удаления.")


async def schedule_remove_old_roles():
    while True:
        await remove_old_roles()
        await asyncio.sleep(86400)  # 86400 секунд = 24 часа


bot.run(TOKEN)
