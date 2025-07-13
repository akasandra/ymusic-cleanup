
from utility import iso_to_utc_timestamp, strip_trailing_dot_zero, value_to_bool
from typing import ContextManager

class DriverBase:

    def _bulk_read(self, wb, min_row: int, max_row: int, column_count: int) -> list:
        raise NotImplementedError()

    def _bulk_write(self, wb, min_row: int, changes: list, columns: list):
        raise NotImplementedError()

    def _open_truncate(self) -> ContextManager:
        raise NotImplementedError()

    def _open_update(self) -> ContextManager:
        raise NotImplementedError()

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

    def get_read_processors(self) -> dict:
        # Per each row, define how each cell value is post-processed (func) using a key in 'processors' 
        processors = self.READ_PROCESSORS.copy()
        for k in self.COLUMN_KEYS:
            if not k in processors:
                processors[k] = lambda value: str(value).strip() if value != None and str(value) else ''

        return processors

    def get_write_processors(self, columns: list) -> dict:
        # Processors per each column we may need or default
        processors = {k: lambda v: v for k in columns}
        for k, f in self.WRITE_PROCESSORS:
            processors[k] = f

        return processors

    def bulk_write(self, changes: list):
        with self._open_truncate() as wb:
            self._bulk_write(wb=wb, min_row=2, changes=changes, columns=self.COLUMN_KEYS)

    def bulk_read(self, no_metadata: bool=False) -> list:
        num_columns = 5 if no_metadata else len(self.COLUMN_KEYS)

        with self._open_update() as wb:
            read_items = self._bulk_read(wb=wb, min_row=2, max_row=None, column_count=num_columns)
            return list(read_items)

    def bulk_update(self, new_changes: list, old_changes: list=None):
        with self._open_update() as wb:

            # Read full current table with likes state to see if any needs update checkbox
            old_changes = self.bulk_read(no_metadata=True) if not old_changes else old_changes

            # Finds newest state per like id
            def get_new_state(c):
                for new in new_changes:
                    if new['artist_id'] == c['artist_id'] and new['album_id'] == c['album_id'] and new['track_id'] == c['track_id']:
                        return new

            # Update likes on old changes (assume order is consistent)
            num_old_rows = 2 + len(old_changes)
            num_updated = 0
            for i, c in enumerate(old_changes):
                # For each of the existing table rows, get the updated state
                new = get_new_state(c)
                if not new:
                    continue

                # For rows with updated like/timestamp, update the row
                if c['like_on'] != new['like_on'] or c['time'] != new['time']:
                    num_updated += 1
                    print('Update row', i+2)
                    self._bulk_write(wb=wb, min_row=2+i, changes=[new], columns=['like_on', 'timestamp'])

            print('Rows updated:', num_updated)

            # The rest of changes are new, write to table
            # Write new table rows (assume metadata is present for new_changes)

            new_changes = new_changes[len(old_changes):]

            # Aggregate rows that are missing
            # Ensure not duplicating rows
            def find_old_entry(c):
                for old in old_changes:
                    if all((old[k] == c[k] for k in ['artist_id', 'album_id', 'track_id'])):
                        yield old

            new_changes = [c for c in new_changes if not any(find_old_entry(c))]

            self._bulk_write(wb=wb, min_row=num_old_rows, changes=new_changes, columns=self.COLUMN_KEYS)
            print('Rows added:', len(new_changes))

# End