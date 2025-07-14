import logging
import gspread
import gspread.utils
from typing import List, Union, Dict, Callable
from source import Source
from utility import iso_to_utc_timestamp
from table_helper import TableHelper
from gspread_formatting import DataValidationRule, BooleanCondition, set_data_validation_for_cell_range, set_frozen
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


# ContextManager
class SpreadsheetContext:
    
    def __init__(self, wb: gspread.Spreadsheet):
        self._wb = wb

    def __enter__(self) -> gspread.Spreadsheet:
        return self._wb

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __getattr__(self, name):
        # Delegate attribute access to the wrapped workbook
        return getattr(self._wb, name)

class GoogleSheetSource(Source, TableHelper):
    """
    Read/Write likes using Google Spreadsheet API and gspread.Client
    """

    def __init__(self, gc: gspread.Client, spreadsheet_url: str, refreshtoken_callback: Callable[[Credentials], None]=None):
        """
        New instance init for a gspread table source (gets, saves data with google spreadsheet).

        Args:
            gc: gspread.Client (authorized/ready)
            spreadsheet_url: URL for the spreadsheet document to work on in this instance
            refreshtoken_callback: Function to call whenever refreshtoken has been updated by the API, to update credentials store
        """
        self.gc = gc
        self.spreadsheet_url = spreadsheet_url
        self.refreshtoken_callback = refreshtoken_callback

    def refresh_token_if_needed(self) -> bool:
        """
        Checks if refreshtoken is valid and credentials need to be updated -> calls the refreshtoken_callback if set.
        Only does so if the client is authorized with OAuth credentials, not service account.

        Returns:
            True if token has changed and the file was updated.
        """
        creds = getattr(self.gc, 'auth', None)
        if creds is None:
            logging.debug("No OAuth credentials found on client; skipping refresh token update.")
            return

        # Check if credentials are OAuth2 Credentials (not service account)
        if not isinstance(creds, Credentials):
            logging.debug("Client is not authorized with OAuth2 credentials; skipping refresh token update.")
            return

        # Refresh token may be updated after refreshing access token
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            if self.refreshtoken_callback:
                self.refreshtoken_callback(creds)
            return True

        return False

    def _open_truncate(self):
        # For OAuth credentials, update refresh token if needed before using the API
        if hasattr(self.gc, 'auth'):
            self.refresh_token_if_needed()

        wb = self.gc.open_by_url(self.spreadsheet_url)

        # Clear all cells content, remove all rows
        logging.warn('Truncate/clear full worksheet')
        wb.sheet1.clear()

        return SpreadsheetContext(wb)
    
    def write_header(self, wb, row: int):
        super().write_header(wb, row)

        sh = wb.sheet1

        logging.info('Create spreadsheet header row and checkbox column')

        # Define the checkbox data validation rule to make checkbox column
        checkbox_rule = DataValidationRule(
            BooleanCondition('BOOLEAN', ['TRUE', 'FALSE']),
            showCustomUi=True
        )
        set_data_validation_for_cell_range(sh, f'A{row+1}:A', checkbox_rule)

        # Header row always visible
        set_frozen(sh, rows=row)

    def _open_update(self):
        # For OAuth credentials, update refresh token if needed before using the API
        if hasattr(self.gc, 'auth'):
            self.refresh_token_if_needed()

        wb = self.gc.open_by_url(self.spreadsheet_url)

        return SpreadsheetContext(wb)

    def _bulk_read(self, wb, min_row: int, max_row: int=None, column_count: int=None) -> list:
        """
        Reads Excel file with changes library.
        Each row describes an artist, album or track. Like is a checkbox.
        """
        # Per each row, define how each cell value is post-processed (func) using a key in 'processors' 
        processors = self.get_read_processors()

        worksheet = wb.sheet1

        logging.debug(min_row)
        if worksheet.row_count < min_row:
            return

        max_row = max_row if max_row else worksheet.row_count
        column_count = column_count if column_count else len(self.COLUMN_KEYS)
        end_col_letter = gspread.utils.rowcol_to_a1(1, column_count)[0]
        range_str = f"A{min_row}:{end_col_letter}{max_row if max_row else ''}"

        # Read every row in range and return rows as key-value dicts
        for row in worksheet.get(range_str):

            # Empty key-value for each column
            c = {k: '' for k in self.COLUMN_KEYS[:column_count]}

            # Fill with cell data and post-processed values
            for idx, value in enumerate(row):
                key = self.COLUMN_KEYS[idx]
                c[key] = processors[key](value)

            # Add unix time 'time' key to the each element
            timestamp = c.get('timestamp')
            c['time'] = iso_to_utc_timestamp(timestamp) if timestamp else 0

            # Break on full empty row
            if all(not v for v in c.values()):
                break
            
            yield c

    def _bulk_write(self, wb, min_row: int, changes: list, columns: list):
        """
        Writes the changes list (list of dicts) back to Excel file
        with updates/additions
        """
        processors = self.get_write_processors(columns)

        worksheet = wb.sheet1

        # Create flat arrays from dicts
        def cell_updates():
            row = min_row
            for c in changes:
                for k in columns:
                    if k in c and k in self.COLUMN_KEYS:
                        value = processors[k](c[k])
                        column_index = self.COLUMN_KEYS.index(k) + 1
                        yield gspread.Cell(row, column_index, value)
                row += 1

        data = list(cell_updates())

        # Resize if needed before write
        desired_rows = min_row + len(changes)
        if worksheet.row_count < desired_rows:
            desired_cols = worksheet.col_count
            worksheet.resize(rows=desired_rows, cols=desired_cols)

        logging.debug('Min row', min_row)
        logging.debug('data len', len(data))

        if data:
            worksheet.update_cells(data)

