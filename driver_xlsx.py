from openpyxl import load_workbook, Workbook
from utility import iso_to_utc_timestamp, strip_trailing_dot_zero, value_to_bool

class XlsxFileDriver:

    # Order of table columns and key names mapping for rows
    COLUMN_KEYS = [
        'like_on',
        'artist_id',
        'album_id',
        'track_id',
        'timestamp',
        'artist',
        'genres',
        'album',
        'track',
        'year',
        'genre'
    ]

    # Transformations after read value for every cell value, by key
    READ_PROCESSORS = {
        'like_on': value_to_bool,
        'artist_id': strip_trailing_dot_zero,
        'album_id': strip_trailing_dot_zero,
        'track_id': strip_trailing_dot_zero,
        'year': strip_trailing_dot_zero
    }

    # Transformations before write value to openpyxl, by key
    WRITE_PROCESSORS = {}

    def __init__(self, filename: str):
        self.filename = filename

    def bulk_read(self) -> list:
        wb = load_workbook(self.filename, data_only=True)
        try:
            ws = wb.active
            read_items = self._bulk_read(ws=ws, min_row=2, max_row=None, column_count=len(self.COLUMN_KEYS))
            return list(read_items)
        finally:
            wb.close()

    def _bulk_read(self, ws, min_row: int, max_row: int, column_count: int) -> list:
        """
        Reads Excel file with changes library.
        Each row describes an artist, album or track. Like is a checkbox.
        """
        # Per each row, define how each cell value is post-processed (func) using a key in 'processors' 
        processors = self.READ_PROCESSORS.copy()
        for k in self.COLUMN_KEYS:
            if not k in processors:
                processors[k] = lambda value: str(value).strip() if value != None and str(value) else ''

        # Read every row in range and return rows as key-value dicts
        for row in ws.iter_rows(min_row=min_row, max_row=max_row, max_col=column_count):

            # Empty key-value for each column
            c = {k: '' for k in self.COLUMN_KEYS[:column_count]}

            # Fill with cell data and post-processed values
            for idx, cell in enumerate(row):
                key = self.COLUMN_KEYS[idx]
                c[key] = processors[key](cell.value)

            # Add unix time 'time' key to the each element
            timestamp = c.get('timestamp')
            c['time'] = iso_to_utc_timestamp(timestamp) if timestamp else 0
            
            yield c

    def bulk_write(self, changes: list):
        wb = Workbook()
        ws = wb.active

        # Header row
        ws.cell(row=1, column=1, value='like')
        ws.cell(row=1, column=2, value='artist_id')
        ws.cell(row=1, column=3, value='album_id')
        ws.cell(row=1, column=4, value='track_id')
        ws.cell(row=1, column=5, value='timestamp')
        ws.cell(row=1, column=6, value='artist')
        ws.cell(row=1, column=7, value='genres')
        ws.cell(row=1, column=8, value='album')
        ws.cell(row=1, column=9, value='track')
        ws.cell(row=1, column=10, value='year')
        ws.cell(row=1, column=11, value='genre')

        self._bulk_write(ws=ws, min_row=2, changes=changes, columns=self.COLUMN_KEYS)

        wb.save(self.filename)
        wb.close()

    def _bulk_write(self, ws, min_row: int, changes: list, columns: list):
        """
        Writes the changes list (list of dicts) back to Excel file
        with updates/additions
        """

        # Processors per each column we may need or default
        processors = {k: lambda v: v for k in columns}
        for k, f in self.WRITE_PROCESSORS:
            processors[k] = f

        # Write the changes
        for row, c in enumerate(changes):
            for column, key in enumerate(columns):
                if not key in c:
                    continue
                value = processors[key](c[key])
                ws.cell(row=min_row+row, column=column+1, value=value)

# End