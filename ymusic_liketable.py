
import re
from yandex_music import Client
from datetime import datetime, timezone
from table_xlsx import XlsxFileDriver as AbstractTableDriver, iso_to_utc_timestamp

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
                0 if not x.get('track_id', '') else 1,
                0 if is_genre_russian(x.get('genres', '')) else 1,
                0 if is_genre_russian(x.get('genre', '')) else 1,
                1 if is_title_latin(x.get('artist', '')) else 0,
                x.get('artist', '').lower(),
                0 if not x.get('album_id', '') else 1,
                x.get('genres', '').lower(),
                x.get('genre', '').lower()
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

        # Find the most recent timestamp in changes file.
        current_time = int(datetime.now(timezone.utc).timestamp())
        changes_max_time = current_time
        if changes:
            changes_max_time = max(d['time'] for d in changes)

        # Find likes set AFTER the file timestamp from API, and re-set checkbox in the file for those
        new_tracks = 0
        new_albums = 0
        new_artists = 0

        online_data_newer = lambda key: (i for i in online_data[key] if iso_to_utc_timestamp(i.timestamp) >= changes_max_time)

        off_changes = [c for c in changes if not c['like_on']]

        for i in online_data_newer('tracks'):
            for c in (c for c in off_changes if c['track_id'] == i.id):
                c['like_on'] = True
                c['timestamp'] = i.timestamp
                new_tracks += 1
        
        for i in online_data_newer('albums'):
            for c in (c for c in off_changes if not c['track_id'] and c['album_id'] == i.album.id and i.album.id):
                c['like_on'] = True
                c['timestamp'] = i.timestamp
                new_albums += 1
        
        for i in online_data_newer('artists'):
            for c in (c for c in off_changes if not c['track_id'] and not c['album_id'] and c['artist_id'] == i.artist.id and i.artist.id):
                c['like_on'] = True
                c['timestamp'] = i.timestamp
                new_artists += 1

        print('Likes ON again (timestamp):\n\tartists %d albums %d tracks %d' % (new_artists, new_albums, new_tracks))

        new_tracks = 0
        new_albums = 0
        new_artists = 0

        # Add artists missings in changes
        for artist in online_data.get('artists'):
            artist_id = artist.artist.id
            genres = ', '.join(artist.artist.genres) if artist.artist.genres else ''
            name = artist.artist.name if artist.artist.name else ''

            match = next(
                (d for d in changes if d['artist_id'] == artist_id and not d['album_id'] and not d['track_id']),
                None
            )
            if not match:
                new_artists += 1
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

        # Add albums missing in changes
        for album in online_data.get('albums'):
            album_id = str(album.album.id)
            genre = album.album.genre
            title = album.album.title

            match = next(
                (d for d in changes if d['album_id'] == album_id and not d['track_id']),
                None
            )
            if not match:
                new_albums += 1
                changes.append({
                    'artist_id': album.album.artists[0].id if album.album.artists else '',
                    'album_id': album_id,
                    'track_id': None,
                    'timestamp': album.timestamp,
                    'like_on': True,
                    'artist': album.album.artists[0].name if album.album.artists else '',
                    'genre': genre if genre else '',
                })

        # Add tracks missing in changes
        for track in online_data.get('tracks'):
            match = next(
                (d for d in changes if d['track_id'] == track.id),
                None
            )
            if not match:
                new_tracks += 1
                changes.append({
                    'artist_id': None,
                    'album_id': track.album_id,
                    'track_id': track.id,
                    'timestamp': track.timestamp,
                    'like_on': True
                })

        print('Likes added NEW:\n\tartists %d albums %d tracks %d' % (new_artists, new_albums, new_tracks))

        # TODO: Always loads something, should not after the initial run and no additions in library ⤵️
        # FIXME: incomplete output data (no album info on tracks and albums)

        # Fetch missing tracks information
        track_ids = [i.get('track_id') for i in changes if i.get('track_id') and (
            not i.get('track') 
            or not i.get('artist')
        )]
        track_ids = list(dict.fromkeys(track_ids))
        tracks = []
        if track_ids:
            print('Need extra information for %d tracks' % len(track_ids))
            tracks = self.client.tracks(with_positions=False, track_ids=track_ids)

        # Fetch missing albums information
        album_ids = [
            i.get('album_id')
            for i in changes
            if not i.get('track_id') and i.get('album_id')
            and not any(a.album.id == i.get('album_id') for a in online_data.get('albums'))
            and not any(track_in_album for track_in_album in tracks if any(a.id == i.get('album_id') for a in track_in_album.albums))
        ]
        album_ids = list(dict.fromkeys(album_ids))
        albums = []
        if album_ids:
            print('Need extra information for %d albums' % len(album_ids))
            albums = self.client.albums(album_ids=album_ids)

        # Substitute incomplete file data (changes) with the online data (albums, tracks)
        for idx, c in enumerate(changes):
            if c['track_id']:
                track = next((t for t in tracks if t.id == c['track_id']), None)
                if track:
                    c['artist_id'] = str(track.artists[0].id)
                    c['album_id'] = str(track.albums[0].id)
                    c['track'] = track.title if not track.version else '%s (%s)' % (track.title, track.version)
            if c.get('album_id'):
                album = next((a for a in albums if a.id == c['album_id']), None)
                if not album:
                    track = next((t for t in tracks if t.albums[0].id == c['album_id']), None)
                    if track:
                        album = track.albums[0]
                if album:
                    c['album'] = album.title if album.title else ''
                    c['genre'] = album.genre if album.genre else ''
                    c['year'] = next((y for y in ( album.original_release_year, album.year, album.release_date[:4] if album.release_date else '') if y), None)
            if c.get('artist_id'):
                artist = next((a.artists[0] for a in albums if a.artists and a.artists[0].id == c['artist_id']), None)
                if not artist:
                    artist = next((t.artists[0] for t in tracks if t.artists[0].id == c['artist_id']), None)
                if not artist:
                    artist = next((a.artist for a in online_data['artists'] if a.artist.id == c['artist_id']), None)
                if artist:
                    c['artist'] = artist.name if artist.name else ''
                    c['genres'] = ', '.join(artist.genres)

            changes[idx] = c

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