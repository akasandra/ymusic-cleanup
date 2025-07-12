
import re
from yandex_music import Client
from datetime import datetime, timezone
from table_xlsx import XlsxFileDriver as AbstractTableDriver, iso_to_utc_timestamp, iso_to_utc_year

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
    return 'rus' in text or 'phonk' in text or 'local' in text

class Worker:
    def __init__(self, token: str, language: str):
        self.token = token
        self.client = Client(token, language=language).init()

    ##aaa
    def sort_changes(self, changes: list) -> list:
        """
        Use sorting in Excel app for HUD. File always gets sorted one way (not using like timestamps)
        """
        return sorted(
            changes,
            key=lambda x: (
                0 if is_genre_russian(x.get('genres', '')) else 1,
                0 if is_genre_russian(x.get('genre', '')) else 1,
                1 if is_title_latin(x.get('artist', '')) else 0,
                x.get('genres'),
                x.get('artist', '').lower(),
                0 if not x.get('album_id', '') else 1,
                0 if not x.get('track_id', '') else 1
            )
        )

    def get_online_data(self) -> dict:
        """
        Use API to read all liked tracks, albums or artists.
        """
        print('API working...')
        
        # Get list of all liked
        tracks = self.client.users_likes_tracks()
        albums = self.client.users_likes_albums()
        artists = self.client.users_likes_artists()

        print('Online Likes: artists %d albums %d tracks %d' % (len(artists), len(albums), len(tracks)))

        # Base sort using timestamps from new to old
        tracks = sorted(tracks, key=lambda item: (item.timestamp, item.album_id), reverse=True)
        albums = sorted(albums, key=lambda item: (item.timestamp, item.album.artists[0].id if item.album.artists else 0), reverse=True)
        artists = sorted(artists, key=lambda item: item.timestamp, reverse=True)

        return {
            'artists': artists,
            'albums': albums,
            'tracks': tracks,
        }

    def get_updated_table(self, online_data: dict, changes: list) -> list:
        """
        Populate changes with missing information from online_data (new tracks, changed info).
        Fetches missing information plus adds new likes if set from online to the changes file.
        """
        num_changed_tracks = 0
        num_changed_albums = 0
        num_changed_artists = 0

        new_track_ids = []
        new_album_ids = []
        new_artist_ids = []

        # Find the most recent timestamp in changes file.
        current_time = int(datetime.now(timezone.utc).timestamp())
        changes_max_time = 0
        if changes:
            changes_max_time = max(d['time'] for d in changes)

        # Find likes set AFTER the file timestamp from API, and re-set checkbox in the file for those
        select_newer_online = lambda key: (i for i in online_data[key] if iso_to_utc_timestamp(i.timestamp) > changes_max_time)

        # Find and update one, with predicate, func, and userdata
        def update_changes_where(predicate, f, i):
            for idx, c in enumerate(changes):
                if predicate(c):
                    product = f(i, c)
                    changes[idx] = product if product else c
                    return True
            return False

        # Func to reset like if it is not set
        def set_like_on(i, c):
            c['like_on'] = True
            c['timestamp'] = i.timestamp
            return c

        # Reset likes if newer online like, for each track/artist/album

        for i in select_newer_online('tracks'):
            if not i.id:
                continue
            if update_changes_where(lambda c: c['track_id'] == str(i.id), set_like_on, i):
                num_changed_tracks += 1
            else:
                new_track_ids.append(i.id)
                changes.append({
                    'artist_id': '',
                    'album_id': '',
                    'track_id': str(i.id),
                    'like_on': True,
                    'timestamp': i.timestamp,
                    'time': iso_to_utc_timestamp(i.timestamp),
                })
        
        for i in select_newer_online('albums'):
            if not i.album.id:
                continue
            if update_changes_where(lambda c: not c['track_id'] and c['album_id'] == str(i.album.id), set_like_on, i):
                num_changed_albums += 1
            else:
                new_album_ids.append(i.album.id)
                changes.append({
                    'artist_id': '',
                    'album_id': str(i.album.id),
                    'track_id': '',
                    'like_on': True,
                    'timestamp': i.timestamp,
                    'time': iso_to_utc_timestamp(i.timestamp),
                })
        
        for i in select_newer_online('artists'):
            if not i.artist.id:
                continue
            if update_changes_where(lambda c: not c['track_id'] and not c['album_id'] and c['artist_id'] == str(i.artist.id), set_like_on, i):
                um_changed_artists += 1
            else:
                new_artist_ids.append(i.artist.id)
                changes.append({
                    'artist_id': str(i.artist.id),
                    'album_id': '',
                    'track_id': '',
                    'like_on': True,
                    'timestamp': i.timestamp,
                    'time': iso_to_utc_timestamp(i.timestamp),
                })

        print('New likes add/set in table:\n\tartists %d albums %d tracks %d' % (num_changed_artists, num_changed_albums, num_changed_tracks))

        # Fetch metadata for new items (artist/track names, year, genre, etc)
        track_info = {}
        album_info = {}
        artist_info = {}

        print('Fetching metadata for new items')

        if new_track_ids:
            data = self.client.tracks(with_positions=False, track_ids=list(set(new_track_ids)))
            track_info = {str(i.id): i for i in data}
            for track in data:
                if track.albums:
                    new_album_ids.append(track.albums[0].id)

        if new_album_ids:
            data = self.client.albums(album_ids=list(set(new_album_ids)))
            album_info = {str(i.id): i for i in data}
            for album in data:
                if album.artists:
                    new_artist_ids.append(album.artists[0].id)

        if new_artist_ids:
            data = self.client.artists(artist_ids=list(set(new_artist_ids)))
            artist_info = {str(i.id): i for i in data}

        print('New metadata: artists %d albums %d tracks %d' % (len(artist_info), len(album_info), len(track_info)))

        # Substitute changes with the metadata (artist/track names, year, genre, etc) for each element that may need this
        for c in changes:
            track = track_info.get(c['track_id']) if c['track_id'] else None

            if track:
                c['album_id'] = str(track.albums[0].id) if track.albums else ''
                c['artist_id'] = str(track.artists[0].id) if track.artists else ''

            album = album_info.get(c['album_id']) if c['album_id'] else None

            if album and album.artists:
                c['artist_id'] = str(album.artists[0].id)
                if len(album.artists) > 1:
                    c['artist'] = ', '.join(i.name for i in album.artists)

            artist = artist_info.get(c['artist_id']) if c['artist_id'] else None

            if artist and not c.get('artist'):
                c['artist'] = artist.name if artist.name else ''
            if artist and not c.get('genres'):
                c['genres'] = ', '.join(artist.genres) if artist.genres else ''

            if album and not c.get('album'):
                
                release_date_year = None
                if album.release_date:
                    release_date_year = iso_to_utc_year(album.release_date)
                year_variants = (album.original_release_year, album.year, release_date_year)
                c['year'] = next((str(y) for y in year_variants if y), '')

                c['genre'] = album.genre if album.genre else ''
                c['album'] = album.title if album.title else ''
                if album.version:
                    c['album'] += ' (%s)' % album.version

            if track and not c.get('track'):
                c['track'] = track.title if track.title else ''
                if track.version:
                    c['track'] += ' (%s)' % track.version

        return self.sort_changes(changes)

    def set_ymusic_likes(self, online_data: dict, changes: list):
        """
        Apply changes from file to online.
        Set new likes and remove likes from online, according to checkboxes in file.
        """

        add_artists = []
        add_albums = []
        add_tracks = []

        rm_artists = []
        rm_albums = []
        rm_tracks = []

        off_changes = [c for c in changes if not c['like_on']]
        on_changes = [c for c in changes if c['like_on']]

        for c in off_changes:
            if c.get('track_id'):
                track = next((t for t in online_data['tracks'] if str(t.id) == c['track_id']), None)
                if track:
                    rm_tracks.append(c['track_id'])
            elif c.get('album_id'):
                album = next((a for a in online_data['albums'] if str(a.album.id) == str(c['album_id'])), None)
                if album:
                    rm_albums.append(c['album_id'])
            elif c.get('artist_id'):
                artist = next((a for a in online_data['artists'] if str(a.artist.id) == c['artist_id']), None)
                if artist:
                    rm_artists.append(c['artist_id'])

        for c in on_changes:
            if c.get('track_id'):
                track = next((t for t in online_data['tracks'] if str(t.id) == c['track_id']), None)
                if not track:
                    add_tracks.append(c['track_id'])
            elif c.get('album_id'):
                album = next((a for a in online_data['albums'] if str(a.album.id) == str(c['album_id'])), None)
                if not album:
                    add_albums.append(c['album_id'])
            elif c.get('artist_id'):
                artist = next((a for a in online_data['artists'] if str(a.artist.id) == c['artist_id']), None)
                if not artist:
                    add_artists.append(c['artist_id'])

        print('Summary of likes to change online:')
        print('\tTotal on ', len(on_changes))
        print('\tTotal off', len(off_changes))
        print('\tRemove likes: artists %d albums %d tracks %d' % (len(rm_artists), len(rm_albums), len(rm_tracks)))
        print('\tAdd likes:    artists %d albums %d tracks %d' % (len(add_artists), len(add_albums), len(add_tracks)))
        print('API working...')

        if rm_tracks:
            self.client.users_likes_tracks_remove(track_ids=rm_tracks)
        if rm_albums:
            self.client.users_likes_albums_remove(album_ids=rm_albums)
        if rm_artists:
            self.client.users_likes_artists_remove(artist_ids=rm_artists)

        if add_tracks:
            self.client.users_likes_tracks_add(track_ids=add_tracks)
        if add_albums:
            self.client.users_likes_albums_add(album_ids=add_albums)
        if add_artists:
            self.client.users_likes_artists_add(artist_ids=add_artists)

        print('This indicates no error!')

# End