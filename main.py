
import logging
from datetime import datetime
from yandex_music import Client

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

token = open('token.txt').read().rstrip('\n')
client = Client(token).init()

print('Session OK')

client.language = 'en'

def build_todo():
    
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
    pass

def dump_changes(todo, changes, filename='./todo.xlsx'):
    pass

def apply_changes(todo, changes, filename='./todo.xlsx'):
    pass