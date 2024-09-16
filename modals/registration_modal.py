import disnake
from disnake.ui import Modal, TextInput

from choices_list import FORMAT

messages_cache = {}


async def clear_messages(inter):
    messages = await inter.channel.history(limit=None).flatten()
    if len(messages) > 1:
        for message in messages[:-1]:
            await message.delete()


class RegistrationModalOne(Modal):
    def __init__(self, title: str, custom_id: str, data: dict, googleSheetsManager):
        input_name = "Team Name" if data["form"] != FORMAT.get("1x1") else "Nickname"

        components = [
            TextInput(
                label=input_name,
                placeholder=input_name,
                custom_id="nickname"
            ),
            TextInput(
                label="Phone",
                placeholder="Phone number",
                custom_id="phone"
            ),
            TextInput(
                label="Branch",
                placeholder="Enter the Branch",
                custom_id="branch"
            ),
        ]

        if data["form"] != FORMAT.get("1x1"):
            components.append(
                TextInput(
                    label="Player's nicknames",
                    placeholder="Nickname1, Nickname2, etc",
                    custom_id="teammates"
                )
            )

        self.data = data
        self.googleSheetsManager = googleSheetsManager
        super().__init__(title=title, custom_id=custom_id, components=components)

    async def callback(self, interaction: disnake.ModalInteraction):
        user_data = {}
        for key, value in interaction.text_values.items():
            user_data[key] = value

        user_data["discord"] = interaction.user.name
        user_data["tournament"] = self.data["tournament"]
        user_data["tournament_name"] = self.data["tournament_name"]

        teammates = ""

        if self.data["form"] != FORMAT.get("1x1"):
            teammates_list = user_data.get("teammates", "").split(",")

            for i, team_tmp in enumerate(teammates_list):
                if i < len(teammates_list) - 1:
                    teammates += team_tmp.strip() + "\n"
                else:
                    teammates += team_tmp.strip()

        users_list = self.googleSheetsManager.get_item_by_field(user_data["tournament"])

        for user in users_list:
            if user[0].lower() == user_data.get("nickname").lower():
                return await interaction.response.send_message("This nickname is already registered, try another one",
                                                               ephemeral=True)
            if user[4].lower() == user_data.get("discord").lower():
                return await interaction.response.send_message("This discord has already been registered, try another "
                                                               "one", ephemeral=True)

        channel_name = interaction.channel.name

        await clear_messages(interaction)
        embed = disnake.Embed(title="List of participants:", color=7339915)

        messages_cache[channel_name] = {}
        messages_cache[channel_name]["users"] = []

        participants = "\n".join(user_item[0] for user_item in users_list if user_item[9] != "DELETED")
        participants += f'\n{user_data.get("nickname")}'

        messages_cache[channel_name]["users"] = [user_item[0] for user_item in users_list]
        messages_cache[channel_name]["users"].append(user_data.get("nickname"))

        embed.description = participants

        await interaction.response.send_message(embed=embed)
        messages_cache[channel_name]["message"] = await interaction.original_message()
        # else:
        #     if user_data.get("nickname").lower() not in [user.lower() for user in
        #                                                  messages_cache[channel_name]["users"]]:
        #         messages_cache[channel_name]["users"].append(user_data.get("nickname"))
        #         old_embed = messages_cache[channel_name]["message"].embeds[0]
        #         new_embed = disnake.Embed(
        #             title=old_embed.title,
        #             color=old_embed.color
        #         )
        #
        #         participants = "\n".join(messages_cache[channel_name]["users"])
        #         new_embed.description = participants
        #
        #         messages_cache[channel_name]["message"] = await messages_cache[channel_name]["message"].edit(
        #             embed=new_embed)
        #
        #     await interaction.response.send_message("Registration is completed!", ephemeral=True)

        role = disnake.utils.get(interaction.guild.roles, name=self.data["tournament_name"])
        if role:
            await interaction.user.add_roles(role)

        await self.googleSheetsManager.add_new_user([
            user_data.get("nickname"), user_data.get("phone"), user_data.get("branch"),
            teammates, user_data.get("discord"), self.data["game"], self.data["form"], user_data["tournament"],
            user_data["tournament_name"]
        ])
