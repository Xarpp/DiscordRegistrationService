import os
import traceback
from time import sleep
import requests
from logger import get_logger
from google_sheets_manager_v2 import GoogleSheetsManager

loggerParticipantService = get_logger(os.path.basename(__file__))


class TournamentParticipantsService:
    pending_tournaments = {}
    complete_tournaments = []
    googleSheetsManager = None
    interrupted = False
    CHALLONGE_API_URL = None
    username = os.getenv("CHALLONGE_LOGIN")
    password = os.getenv("CHALLONGE_API_KEY")
    headers = {'User-Agent': 'Chrome'}

    def __init__(self):
        self.interrupted = False
        self.googleSheetsManager = GoogleSheetsManager(os.getenv("SHEET_ID"))

    def get_tournament_data(self, tournament_id):
        response = requests.get(f"https://api.challonge.com/v1/tournaments/{tournament_id}.json",
                                auth=(self.username, self.password), headers=self.headers)
        return response.json()

    def get_participants_data(self, tournament_id):
        participants = []
        response = requests.get(f"https://api.challonge.com/v1/tournaments/{tournament_id}/participants.json",
                                auth=(self.username, self.password), headers=self.headers)
        response_json = response.json()

        for participant in response_json:
            participants.append(participant['participant'])

        return participants

    def del_participant_from_tournament(self, tournament_id, participant_id):
        requests.delete(f"https://api.challonge.com/v1/tournaments/{tournament_id}/participants/{participant_id}.json",
                        auth=(self.username, self.password), headers=self.headers)

    def add_participant_from_tournament(self, tournament_id, username):
        data = {
            "participant": {
                "name": username
            }
        }
        participant = requests.post(f"https://api.challonge.com/v1/tournaments/{tournament_id}/participants.json",
                                    auth=(self.username, self.password), headers=self.headers, json=data)
        return participant.json()['participant']

    def run(self):
        while True:
            try:
                loggerParticipantService.debug("Participant service was started")
                while not self.interrupted:
                    data = self.googleSheetsManager.get_users_data(os.getenv("USERS_DATABASE_TABLE"))
                    for index, google_participant_item in enumerate(data):
                        if not google_participant_item:
                            continue
                        if not (google_participant_item[7] or google_participant_item[0]):
                            continue

                        tournament_id = google_participant_item[7]
                        username = google_participant_item[0]
                        add_flag = google_participant_item[9]

                        is_participant_added = True if add_flag == "TRUE" else False

                        if tournament_id in self.complete_tournaments:
                            loggerParticipantService.debug(f"Tournament {tournament_id} is already complete")
                            continue
                        tournament_data = self.get_tournament_data(tournament_id)
                        if tournament_data['tournament']['state'] == "pending":
                            participants = self.pending_tournaments.get(tournament_id, None)

                            if participants is None:
                                participants = self.get_participants_data(tournament_id)
                                self.pending_tournaments[tournament_id] = participants

                            participant = next((participant for participant in participants
                                                if participant["name"].lower() == username.lower()), None)

                            if participant:
                                if not is_participant_added:
                                    self.del_participant_from_tournament(tournament_id, participant['id'])
                                    participants.remove(participant)
                                    loggerParticipantService.info(f"User {participant['name']} was deleted from tournament"
                                                                  f" {tournament_id}")
                            elif not participant:
                                if is_participant_added:
                                    new_participant = self.add_participant_from_tournament(tournament_id, username)

                                    participants.append(new_participant)
                                    loggerParticipantService.info(f"User {new_participant['name']} was added in tournament"
                                                                  f" {tournament_id}")
                            if add_flag == "DELETED":
                                loggerParticipantService.info(f'{add_flag} - {index+2}')
                                self.googleSheetsManager.delete_row(index+2)
                        else:
                            self.complete_tournaments.append(tournament_id)
                    sleep(5)
            except Exception as e:
                exception_info = traceback.format_exc()
                loggerParticipantService.error(f"Сервис столкнулся с ошибкой:\n{e}\n{exception_info}")
                loggerParticipantService.info("Попытка перезапуска сервиса через 30 секунд...")
                sleep(30)  # Пауза перед перезапуском сервиса
                continue


if __name__ == '__main__':
    tournamentParticipantsService = TournamentParticipantsService()
    tournamentParticipantsService.run()
