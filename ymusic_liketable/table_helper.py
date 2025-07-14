import re
from typing import List
from .utility import iso_to_utc_timestamp, strip_trailing_dot_zero, value_to_bool

class TableHelper:
    """
    Data cleaning and read/write helper.

    raw values:

        v = cell.value

    clean value:

        v = processor(cell.value)

    Editing tables (xlsx, google, etc) may yield weird actual values like '50 ' or '50.0' instead of '50', etc.
    """

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

    @classmethod
    def sort(cls, table_data: List[dict]) -> List[dict]:
        """
        Convenient sorting for table data.
        """
        return sorted(
            table_data,
            key=lambda x: (
                0 if is_genre_russian(x.get('genres', '')) else 1,
                1 if is_title_latin(x.get('artist', '')) else 0,

                x.get('artist', '').lower(),

                0 if not x.get('album_id') else 1,
                int(x['year']) if 'year' in x and x['year'] else 0,
                0 if is_genre_russian(x.get('genre', '')) else 1,
                
                0 if not x.get('track_id') else 1,
                x.get('track_id', '')
            )
        )

# Allowed characters:
# - Basic Latin letters (A-Z, a-z)
# - Latin-1 Supplement letters with accents (À-ÿ, including ñ, á, é, etc.)
# - Spaces and common punctuation: - ( ) . , & and apostrophe '
# Note: \u00C0-\u00FF covers Latin-1 Supplement block (accented chars)
# Apostrophe added as it is common in titles
NON_LATIN_PATTERN = re.compile(r"[^A-Za-z\u00C0-\u00FF\s\-\(\)\.,&']+")

def is_title_latin(text: str) -> bool:
    if not text:
        return False
    # Return True if no disallowed characters found
    return not bool(NON_LATIN_PATTERN.search(text))

def is_genre_russian(text: str) -> bool:
    if not text:
        return False
    # To find obvious russian music genres
    return 'rus' in text or 'phonk' in text or 'local' in text