# %%
from ymusic_cleanup import client, get_online_data, load_changes, update_changes, dump_changes, set_likes_changes

# %%
try:
    changes = load_changes()
except FileNotFoundError:
    print("File not found, starting with empty changes list.")
    changes = []

# %%
online_data = get_online_data()

# %%
changes = update_changes(online_data, changes)

# %%
dump_changes(changes)

# %%
set_likes_changes(online_data, changes)


