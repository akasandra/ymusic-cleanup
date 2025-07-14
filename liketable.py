
import logging
from typing import Tuple
from yandex_music import Client
from datetime import datetime, timezone
from utility import iso_to_utc_timestamp, iso_to_utc_year

class Liketable:
    def __init__(self, token: str, language: str):
        self.token = token
        self.client = Client(token, language=language).init()

    def get_online_data(self) -> dict:
        """
        Use API to read all liked tracks, albums or artists.
        """
        logging.info('API working...')

        # API data state timestamp
        now_utc = datetime.now(timezone.utc)
        
        # Get list of all liked
        tracks = self.client.users_likes_tracks()
        albums = self.client.users_likes_albums()
        artists = self.client.users_likes_artists()

        logging.info('Online Likes: artists %d albums %d tracks %d', len(artists), len(albums), len(tracks))

        # Base sort using timestamps from new to old
        tracks = sorted(tracks, key=lambda item: (item.timestamp, item.album_id), reverse=True)
        albums = sorted(albums, key=lambda item: (item.timestamp, item.album.artists[0].id if item.album.artists else 0), reverse=True)
        artists = sorted(artists, key=lambda item: item.timestamp, reverse=True)

        return {
            'artists': artists,
            'albums': albums,
            'tracks': tracks,
            'timestamp': now_utc.isoformat(),
            'time': int(now_utc.timestamp()),
        }
 
    def upload_changed_likes(self, online_data: dict, changes: list) -> dict:
        """
        Apply changes from file to online.
        Set new likes and remove likes from online, according to checkboxes in file.

        Tells some stats.
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
                if not any(t for t in online_data['tracks'] if str(t.id) == c['track_id']):
                    continue

                rm_tracks.append(c['track_id'])

            elif c.get('album_id'):
                if not any(a for a in online_data['albums'] if str(a.album.id) == str(c['album_id'])):
                    continue
                
                rm_albums.append(c['album_id'])

            elif c.get('artist_id'):
                if not any(a for a in online_data['artists'] if str(a.artist.id) == c['artist_id']):
                    continue
                
                rm_artists.append(c['artist_id'])

            else:
                continue

            # Clear timestamp so that we know from table, like is confirmed to be unset
            c.update({
                'time': 0,
                'timestamp': ''
            })

        for c in on_changes:
            if c.get('track_id'):
                if any(t for t in online_data['tracks'] if str(t.id) == c['track_id']):
                    continue
                
                add_tracks.append(c['track_id'])

            elif c.get('album_id'):
                if any(a for a in online_data['albums'] if str(a.album.id) == str(c['album_id'])):
                    continue

                add_albums.append(c['album_id'])

            elif c.get('artist_id'):
                if any(a for a in online_data['artists'] if str(a.artist.id) == c['artist_id']):
                    continue
                
                add_artists.append(c['artist_id'])

            else:
                continue

            # Approximate the real then-API timestamp and reflect in the new table data
            c.update({
                'time': online_data['time'],
                'timestamp': online_data['timestamp']
            })

        logging.info('API to-do:')
        logging.info('\tRemove like: artists %d albums %d tracks %d', len(rm_artists), len(rm_albums), len(rm_tracks))
        logging.info('\tAdd like:    artists %d albums %d tracks %d', len(add_artists), len(add_albums), len(add_tracks))

        # No need to do anything if no likes to upload
        if any((rm_tracks, rm_albums, rm_artists, add_tracks, add_albums, add_artists)):
            logging.info('API working...')

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

            logging.info('Table status: like %d not %d', len(on_changes), len(off_changes))
            logging.info('This indicates no error!')

        return {
            'set': len(add_tracks + add_albums + add_artists),
            'unset': len(rm_tracks + rm_albums + rm_artists),
        }

    def import_changes(self, online_data: dict, changes: list) -> dict:
        """
        Populate changes with updated information according to the online_data.
        Changes like_on and timestamps on the changed likes from current data.
        Appends new likes to the end, if any.

        Returns stats array with counters for unset/change/new
        """
        old_len = len(changes)

        # Reflect likes removed from Yandex Music app
        num_unset = self._import_unset_likes(online_data, changes)

        # Find new likes from Yandex.Music and add to changes
        state = self._import_new_likes(online_data, changes)

        # Fetch metadata for new items (artist/track names, year, genre, etc)
        self._import_new_metadata(state, changes)
        
        # Tells stats for final changes
        return {
            'unset': num_unset,
            'set': state[0],
            'new': len(changes) - old_len
        }

    def _import_unset_likes(self, online_data: dict, changes: list) -> int:
        num_unset = 0

        liked_track_ids = [str(i.id) for i in online_data['tracks']]
        liked_album_ids = [str(i.album.id) for i in online_data['albums']]
        liked_artist_ids = [str(i.artist.id) for i in online_data['artists']]

        def found_in_online_data(c):
            if c['track_id']:
                return c['track_id'] in liked_track_ids
            elif c['album_id']:
                return not c['track_id'] and c['album_id'] in liked_album_ids
            elif c['artist_id']:
                return not c['album_id'] and not c['track_id'] and c['artist_id'] in liked_artist_ids
            else:
                return False

        for c in changes:
            if c['like_on'] and c['timestamp'] and not found_in_online_data(c):
                c['like_on'] = False
                c['timestamp'] = ''
                c['time'] = 0
                num_unset += 1

        logging.info('Likes unset in table from online: %d', num_unset)
        return num_unset

    def _import_new_likes(self, online_data: dict, changes: list) -> Tuple:
        new_track_ids = []
        new_album_ids = []
        new_artist_ids = []

        num_set = 0

        # Find the most recent timestamp in changes file.
        changes_max_time = 0
        if changes:
            changes_max_time = max(d['time'] for d in changes)

        # Find likes set AFTER the file timestamp from API, and re-set checkbox in the file for those
        select_newer_online = lambda key: (i for i in online_data[key] if iso_to_utc_timestamp(i.timestamp) > changes_max_time)

        # Find and update one, with predicate, func, and userdata
        def update_changes_where(predicate, f, i=None):
            for idx, c in enumerate(changes):
                if predicate(c):
                    product = f(i, c)
                    changes[idx] = product if product else c
                    return True
            return False

        # Func to reset like
        def set_like_on(i, c):
            c['like_on'] = True
            c['timestamp'] = i.timestamp
            c['time'] = iso_to_utc_timestamp(i.timestamp)
            return c
        
        for i in select_newer_online('artists'):
            if not i.artist.id:
                continue
            if update_changes_where(lambda c: not c['track_id'] and not c['album_id'] and c['artist_id'] == str(i.artist.id), set_like_on, i):
                num_set += 1
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
        
        for i in select_newer_online('albums'):
            if not i.album.id:
                continue
            if update_changes_where(lambda c: not c['track_id'] and c['album_id'] == str(i.album.id), set_like_on, i):
                num_set += 1
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

        for i in select_newer_online('tracks'):
            if not i.id:
                continue
            if update_changes_where(lambda c: c['track_id'] == str(i.id), set_like_on, i):
                num_set += 1
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

        logging.info('New likes add/set in table: %d', num_set)

        return num_set, new_track_ids, new_album_ids, new_artist_ids

    def _import_new_metadata(self, state: Tuple, changes: list):
        _, new_track_ids, new_album_ids, new_artist_ids = state

        # No need to do anything if no metadata to request
        if not any(c for c in state[1:]):
            return

        track_info = {}
        album_info = {}
        artist_info = {}

        logging.info('API working...')

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

        logging.info('New metadata: artists %d albums %d tracks %d', len(artist_info), len(album_info), len(track_info))

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


# End