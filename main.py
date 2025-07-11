
import logging
from yandex_music import Client
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from datetime import datetime
import re

logging.basicConfig(
    level=logging.WARN,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

token = open('token.txt').read().rstrip('\n')
client = Client(token, language='en').init()

print('Session OK')


def is_english(text: str) -> bool:
    if not text:
        return False
    # This regex matches any non-English character (outside basic Latin ranges)
    # Adjust pattern to allow spaces and basic punctuation if needed
    return not bool(re.findall(r"[^\u0000-\u007F]+", text))


def is_russian_genre(text: str) -> bool:
    if not text:
        return False
    return 'rus' in text or 'phonk' in text

def get_online_data():
    
    # Get list of all liked tracks
    tracks = client.users_likes_tracks()
    print('Number of liked tracks: %d' % len(tracks))

    # Get list of all liked albums
    albums = client.users_likes_albums()
    print('Number of liked albums: %d' % len(albums))

    # Get list of all liked artists
    artists = client.users_likes_artists()
    print('Number of liked artists: %d' % len(artists))

    # Sort tracks by most recently 'liked'
    tracks = sorted(tracks, key=lambda item: (item.timestamp, item.album_id), reverse=True)

    # Sort albums by most recently 'liked'
    albums = sorted(albums, key=lambda item: (item.timestamp, item.album.artists[0].id if item.album.artists else 0), reverse=True)

    # Sort artists by most recently 'liked'
    artists = sorted(artists, key=lambda item: item.timestamp, reverse=True)

    return {
        'artists': artists,
        'albums': albums,
        'tracks': tracks,
    }

def load_changes(filename='./todo.xlsx') -> dict:
    """
    Reads Excel file with checkbox (boolean) in column A and string in column B.
    Returns list of dicts: [{False: "string1"}, {True: "string2"}, ...]
    """
    wb = load_workbook(filename, data_only=True)
    ws = wb.active
    
    changes = []
    for row in ws.iter_rows(min_row=2, max_col=11):
        like_on = row[0].value
        artist_id = row[1].value
        album_id = row[2].value
        track_id = row[3].value
        timestamp = row[4].value
        artist = row[5].value
        genres = row[6].value
        album = row[7].value
        track = row[8].value
        year = row[9].value
        genre = row[10].value
        
        # Normalize boolean value: openpyxl may read Excel TRUE/FALSE as str or bool
        if isinstance(like_on, str):
            like_on = like_on.strip().upper() == 'TRUE'
        else:
            like_on = bool(like_on)
        
        # If string cell is None, convert to empty string for consistency
        artist_id = str(artist_id) if artist_id is not None else ""
        album_id = str(album_id) if album_id is not None else ""
        track_id = str(track_id) if track_id is not None else ""
        timestamp = str(timestamp) if timestamp is not None else ""
        artist = str(artist) if artist is not None else ""
        genres = str(genres) if genres is not None else ""
        album = str(album) if album is not None else ""
        track = str(track) if track is not None else ""
        year = str(year) if year is not None else ""
        genre = str(genre) if genre is not None else ""
        
        changes.append({
            'artist_id': artist_id,
            'album_id': album_id,
            'track_id': track_id,
            'timestamp': timestamp,
            'like_on': like_on,
            'artist': artist,
            'genres': genres,
            'album': album,
            'track': track,
            'year': year,
            'genre': genre,
        })
    
    return changes

def dump_changes(online_data, changes, filename='./todo.xlsx'):
    """
    Writes the changes list (list of dicts) back to Excel file.
    Adds one extra row at the top with hardcoded checkbox and string.
    Each row: checkbox (boolean) in column A, string in column B.
    """
    wb = Workbook()
    ws = wb.active

    # Header row
    ws.cell(row=1, column=1, value='like')
    ws.cell(row=1, column=2, value='artist_id')
    ws.cell(row=1, column=3, value='album_id')
    ws.cell(row=1, column=4, value='track_id')
    ws.cell(row=1, column=5, value='like_time')
    ws.cell(row=1, column=6, value='artist')
    ws.cell(row=1, column=7, value='genres')
    ws.cell(row=1, column=8, value='album')
    ws.cell(row=1, column=9, value='track')
    ws.cell(row=1, column=10, value='year')
    ws.cell(row=1, column=11, value='genre')

    # Merge missing artists
    for artist in online_data.get('artists'):
        artist_id = artist.artist.id
        genres = ', '.join(artist.artist.genres) if artist.artist.genres else ''
        name = artist.artist.name if artist.artist.name else ''

        match = next(
            (d for d in changes if d['artist_id'] == artist_id and not d['track_id']),
            None
        )
        if not match:
            changes.append({
                'artist_id': artist_id,
                'album_id': None,
                'track_id': None,
                'timestamp': artist.timestamp,
                'like_on': True,
                'artist': name,
                'genres': genres,
                'genre': artist.artist.genres[0] if artist.artist.genres else ''
            })

    # Merge missing albums
    for album in online_data.get('albums'):
        album_id = album.album.id
        genre = ', '.join(album.album.genre) if album.album.genre else ''
        title = album.album.title if album.album.title else ''

        match = next(
            (d for d in changes if d['album_id'] == album_id and not d['track_id']),
            None
        )
        if not match:
            changes.append({
                'artist_id': album.album.artists[0].id if album.album.artists else '',
                'album_id': album_id,
                'track_id': None,
                'timestamp': album.timestamp,
                'like_on': True,
                'artist': album.album.artists[0].name if album.album.artists else '',
                'genres': '',
                'genre': genre
            })

    # Merge missing tracks
    for track in online_data.get('tracks'):
        match = next(
            (d for d in changes if d['track_id'] == track.id),
            None
        )
        if not match:
            changes.append({
                'artist_id': None,
                'album_id': track.album_id,
                'track_id': track.id,
                'timestamp': track.timestamp,
                'like_on': True,
                'artist': '',
                'genres': '',
                'genre': ''
            })

    # Example: sorting changes by 'name' and then by 'genres'
    changes = sorted(
        changes,
        key=lambda x: (
            0 if not x.get('track_id', '') else 1,
            0 if is_russian_genre(x.get('genres', '')) else 1,
            0 if is_russian_genre(x.get('genre', '')) else 1,
            1 if is_english(x.get('artist', '')) else 0,
            x.get('artist', '').lower(),
            0 if not x.get('album_id', '') else 1,
            x.get('genres', '').lower(),
            x.get('genre', '').lower()
        )
    )

    def album_title(change):
        if change['album_id']:
            return 'album_title'

    def track_title(change):
        if change['track_id']:
            return 'track_title'

    def album_year(change):
        if change['album_id']:
            return 'album_year'

    # Write the changes
    for row_idx, change in enumerate(changes, start=2):
        ws.cell(row=row_idx, column=1, value=change.get('like_on'))
        ws.cell(row=row_idx, column=2, value=change.get('artist_id'))
        ws.cell(row=row_idx, column=3, value=change.get('album_id'))
        ws.cell(row=row_idx, column=4, value=change.get('track_id'))
        ws.cell(row=row_idx, column=5, value=change.get('timestamp'))
        ws.cell(row=row_idx, column=6, value=change.get('artist'))
        ws.cell(row=row_idx, column=7, value=change.get('genres'))
        ws.cell(row=row_idx, column=8, value=album_title(change))
        ws.cell(row=row_idx, column=9, value=track_title(change))
        ws.cell(row=row_idx, column=10, value=album_year(change))

    wb.save(filename)

def apply_changes(online_data, changes, filename='./todo.xlsx'):
    pass