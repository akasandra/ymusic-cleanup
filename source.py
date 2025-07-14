
import logging
from typing import ContextManager, List

class Source:
    """
    Base for table input/output source. Like XLSX, google, etc.

    Provides high-level bulk_read, bulk_write (replace data) and bulk_update.

    See Not Implemented methods.
    """

    # BEGIN Abstract To-Do

    def _open_truncate(self) -> ContextManager:
        """
        Get internal resource "wb" (read/write) as context manager protocol.
        Cleanup resources if needed in __exit__

        Truncate mode: All data must be erased before subsequent writes will provide from zero.

        Returns:
            "wb" resource to use for read/write by _methods.
        """
        raise NotImplementedError()

    def _open_update(self) -> ContextManager:
        """
        Get internal resource "wb" (read/write) as context manager protocol.
        Cleanup resources if needed in __exit__

        Update mode: Do not erase existing data, if any

        Returns:
            "wb" resource to use for read/write by _methods.
        """
        raise NotImplementedError()

    def _bulk_read(self, wb, min_row: int, max_row: int, column_count: int) -> List[dict]:
        """
        Read N rows from "wb" resource and get list of dicts (dict = like item),
        with starting row number and max rows/cols count (if used)

        May return many-many likes at once.
        """
        raise NotImplementedError()

    def _bulk_write(self, wb, min_row: int, changes: List[dict], columns: List[str]):
        """
        Re/write N rows to "wb" resource, given list of dicts (dict = like item),
        with starting row number and list of keys to re/write.
        """
        raise NotImplementedError()

    # END Abstract To-Do

    # Column order and key mappings
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

    # no_metadata reading must only provide ids, like_on, timestamp from each row.
    MIN_COLUMNS = 5

    def bulk_read(self, no_metadata: bool=False) -> List[dict]:
        """
        Read full data.

        Args:
            no_metadata: only read ids. Efficient for cases when data is not needed and job is possible.

        Returns:
            List of likes from table as dicts.
        """
        num_columns = self.MIN_COLUMNS if no_metadata else len(self.COLUMN_KEYS)

        with self._open_update() as wb:
            read_items = self._bulk_read(wb=wb, min_row=2, max_row=None, column_count=num_columns)
            return list(read_items)

    def bulk_write(self, changes: List[dict]):
        """
        Truncate and replace table data with the provided list.
        """
        with self._open_truncate() as wb:
            self.write_header(wb, 1)
            self._bulk_write(wb=wb, min_row=2, changes=changes, columns=self.COLUMN_KEYS)

    def write_header(self, wb, row: int):
        """
        Re/creates table header (row number for header row is specified).
        """
        data = {k: k for k in self.COLUMN_KEYS}
        self._bulk_write(wb, min_row=row, changes=[data], columns=self.COLUMN_KEYS)

    def bulk_update(self, new_data: List[dict], cached_old_data: List[dict]=None):
        """
        Open existing file. Use (or get) the old data and compare:
            - For updated entries, change row data (like_on, timestamp only)
            - For new entries (id not in the table), append to the end of table
        """
        with self._open_update() as wb:

            # Read full current table with likes state to see if any needs update checkbox
            cached_old_data = self.bulk_read(no_metadata=True) if not cached_old_data else cached_old_data

            # Finds newest state per like id
            def get_new_state(c):
                for new in new_data:
                    if new['artist_id'] == c['artist_id'] and new['album_id'] == c['album_id'] and new['track_id'] == c['track_id']:
                        return new

            # Aggregate rows that are missing
            # Ensure not duplicating rows
            def find_old_entry(c):
                for old in cached_old_data:
                    if all((old[k] == c[k] for k in ['artist_id', 'album_id', 'track_id'])):
                        yield old

            # Update likes on old changes (assume order is consistent)
            num_old_rows = 2 + len(cached_old_data)
            num_updated = 0
            for i, c in enumerate(cached_old_data):
                # For each of the existing table rows, get the updated state
                new = get_new_state(c)
                if not new:
                    continue

                # TODO: optimize by joining calls into one range

                # For rows with updated like/timestamp, update the row
                if c['like_on'] != new['like_on'] or c['timestamp'] != new['timestamp']:
                    num_updated += 1
                    logging.debug('Update row', i+2)
                    self._bulk_write(wb=wb, min_row=2+i, changes=[new], columns=['like_on', 'timestamp'])

            logging.debug('Rows updated:', num_updated)

            # The rest of changes are new likes
            # Write new table rows (assume metadata is present for new_data)

            # Get the rows remainder
            new_data = new_data[len(cached_old_data):]
            if new_data:
                # Safety: checks if remainder rows don't duplicate likes.
                new_data = [c for c in new_data if not any(find_old_entry(c))]

                # Write the remainder
                self._bulk_write(wb=wb, min_row=num_old_rows, changes=new_data, columns=self.COLUMN_KEYS)

            logging.debug('Rows added:', len(new_data))

# End