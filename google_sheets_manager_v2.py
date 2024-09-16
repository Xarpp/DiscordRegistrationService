import os
from dotenv import load_dotenv, find_dotenv
import gspread
from google.oauth2.service_account import Credentials
from logger import get_logger
from gspread_formatting import *

load_dotenv(find_dotenv(), verbose=True, override=True)

loggerSheet = get_logger(os.path.basename(__file__))


class GoogleSheetsManager:
    SCOPES = [os.getenv('SCOPES')]

    def __init__(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.sheet = None
        service_account_files = [os.getenv('SHEET_SERVICE_ACCOUNT_FILE'),
                                 os.getenv('SHEET_SERVICE_ACCOUNT_FILE_RESERVE')]

        for file in service_account_files:
            try:
                loggerSheet.info(f"Attempting connection with {file}")
                creds = Credentials.from_service_account_file(file,
                                                              scopes=self.SCOPES)
                client = gspread.authorize(creds)
                self.sheet = client.open_by_key(spreadsheet_id)
                loggerSheet.info("Connection to Google Sheets was successful")
                break
            except Exception as error:
                loggerSheet.error(f'An error occurred with {file}: {error}')
                continue

        if self.sheet is None:
            loggerSheet.critical("Failed to connect to any service account")

    async def write_data(self, range_name, values):
        sheet_name, cell_range = range_name.split('!')
        worksheet = self.sheet.worksheet(sheet_name)
        cell_list = worksheet.range(cell_range)

        for i, cell in enumerate(cell_list):
            cell.value = values[i]

        worksheet.update_cells(cell_list)

        validation_rule = DataValidationRule(
            BooleanCondition('BOOLEAN', ['TRUE', 'FALSE']),
            showCustomUi=True)
        set_data_validation_for_cell_range(worksheet, f"J{cell_list[-1].row}", validation_rule)

    def get_item_by_field(self, value):
        all_values = self.get_users_data(os.getenv("USERS_DATABASE_TABLE"))
        matching_rows = []

        for row in all_values:
            if value in row:
                matching_rows.append(row)

        return matching_rows

    async def append_to_first_empty_row(self, values):
        sheet_name = os.getenv("USERS_DATABASE_TABLE").split("!")[0]
        worksheet = self.sheet.worksheet(sheet_name)

        col_values = worksheet.col_values(1)
        first_empty_row = len(col_values) + 1
        for index, item in enumerate(col_values, start=1):
            if item == '':
                first_empty_row = index

        await self.write_data(f"{sheet_name}!A{first_empty_row}:I{first_empty_row}", values)
        loggerSheet.debug("New row has been added to the first empty row of the table")

    def get_users_data(self, range_data):
        loggerSheet.debug("Getting user data")
        sheet_name, cell_range = range_data.split('!')
        worksheet = self.sheet.worksheet(sheet_name)
        values = worksheet.get(cell_range)

        if not values:
            loggerSheet.debug("No data found")
        else:
            loggerSheet.debug("Data received successfully")
            filtered_items = get_filtered_data(values)
            return filtered_items

    async def add_new_user(self, user_data):
        loggerSheet.debug("Adding a new user")
        await self.append_to_first_empty_row(user_data)
        loggerSheet.debug("User added successfully")

    async def set_deleted_from_tournament(self, discord, tournament):
        values = self.get_users_data(os.getenv("USERS_DATABASE_TABLE"))
        sheet_name = os.getenv("USERS_DATABASE_TABLE").split("!")[0]
        for index, row in enumerate(values):
            if row and row[7] == tournament and row[4] == discord:
                row[9] = "DELETED"
                await self.write_data(f"{sheet_name}!A{index + 2}:J{index + 2}", row)
                return True
        return False

    def delete_row(self, row_index):
        sheet_name = os.getenv("USERS_DATABASE_TABLE").split("!")[0]
        worksheet = self.sheet.worksheet(sheet_name)
        worksheet.delete_rows(row_index)
        loggerSheet.debug(f"Row {row_index} has been deleted from the table")


def get_filtered_data(values):
    filtered_data = []
    for item in values:
        if "DELETED" in item:
            continue
        if item[0] == '':
            continue
        filtered_data.append(item)
    return filtered_data


if __name__ == '__main__':
    googleSheetManager = GoogleSheetsManager(os.getenv("SHEET_ID"))
    values = googleSheetManager.get_users_data(os.getenv("USERS_DATABASE_TABLE"))
