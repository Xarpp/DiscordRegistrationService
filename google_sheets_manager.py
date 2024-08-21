import os.path
from dotenv import load_dotenv, find_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from logger import get_logger

load_dotenv(find_dotenv(), verbose=True, override=True)

loggerSheet = get_logger(os.path.basename(__file__))


class GoogleSheetsManager:
    SCOPES = [os.getenv('SCOPES')]

    def __init__(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.sheet = None
        self.service = None

        service_account_files = [os.getenv('SHEET_SERVICE_ACCOUNT_FILE'),
                                 os.getenv('SHEET_SERVICE_ACCOUNT_FILE_RESERVE')]

        for file in service_account_files:
            try:
                loggerSheet.info(f"Attempting connection with {file}")
                creds = Credentials.from_service_account_file(file,
                                                              scopes=self.SCOPES)
                self.service = build('sheets', 'v4', credentials=creds)
                self.sheet = self.service.spreadsheets()
                loggerSheet.info("Connection to Google Sheets was successful")
                break
            except HttpError as error:
                loggerSheet.error(f'An error occurred with {file}: {error}')
                continue

        if self.service is None:
            loggerSheet.critical("Failed to connect to any service account")

    def write_data(self, range_name, values):
        body = {
            'values': [values]
        }
        result = self.sheet.values().update(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', body=body).execute()
        loggerSheet.debug(f'Writing data. Range - {range_name}. {result.get("updatedCells")} cells updated')

    def get_item_by_field(self, find_item, index):
        find_items = []
        data = self.get_users_data(os.getenv("USERS_DATABASE_TABLE"))

        if data is None:
            return find_items

        for item in data:
            if not item:
                continue
            if item[index] == find_item:
                find_items.append(item)
        return find_items

    def append_to_last_empty_row(self, range_name, values):
        body = {
            'values': [values]
        }
        self.sheet.values().append(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='RAW', insertDataOption='INSERT_ROWS', body=body).execute()
        loggerSheet.debug("New row has been added to the table")

    def get_users_data(self, range_data):
        loggerSheet.debug("Getting user data")
        result = self.sheet.values().get(spreadsheetId=self.spreadsheet_id, range=range_data).execute()
        values = result.get('values', [])
        if not values:
            loggerSheet.debug("No data found")
        else:
            loggerSheet.debug("Data received successfully ")
            return values

    def add_new_user(self, sheet, user_data):
        loggerSheet.debug("Adding a new user")
        self.append_to_last_empty_row(sheet, user_data)
        loggerSheet.debug("User added successfully")

    def set_deleted_from_tournament(self, discord, tournament):
        values = self.get_users_data(os.getenv("USERS_DATABASE_TABLE"))
        sheet_name = os.getenv("USERS_DATABASE_TABLE").split("!")[0]
        for index, row in enumerate(values):
            if row and row[7] == tournament and row[4] == discord:
                row[9] = "DELETED"
                self.write_data(f"{sheet_name}!A{index+2}:J{index+2}", row)
                return True
        return False

    def delete_row(self, row_index):
        sheet_name = os.getenv("USERS_DATABASE_TABLE").split("!")[0]
        delete_range = f"{sheet_name}!A{row_index}:J{row_index}"
        self.sheet.values().clear(spreadsheetId=self.spreadsheet_id, range=delete_range).execute()
