# %%
import logging
from copy import deepcopy
from liketable import Liketable
from table_helper import TableHelper
from source_google import GoogleSheetSource
from google_helper import GoogleHelper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# %%
# IAM credentials file from Google Console (Service account or OAuth2)
google_creds_file = 'creds.json'

# Replace with your link to google sheets document
# Must be shared with service account client_email
table_url = 'https://docs.google.com/spreadsheets/d/1nLZUKSeqYuskrF5mHOer_BiCWjh84JHHb0BFq53Z2lw/edit?gid=0#gid=0'

# Assume Google Credetials are for Service Acount
# For OAuth2, set client_id and client_secret
gc = GoogleHelper.client_json_creds(filename=google_creds_file, client_id=None, client_secret=None)

# For OAuth2 mode with Google APIs,
# creds.json may need to be updated if refresh token has changed during lifetime.
cb = GoogleHelper.make_file_update_function(google_creds_file)

source = GoogleSheetSource(gc=gc, spreadsheet_url=table_url, refreshtoken_callback=cb)

# %%
yandex_token = open('token.txt').read().strip('\n')

w = Liketable(token=yandex_token, language='en')

# %%
table_data = source.bulk_read(no_metadata=True)

old_data = deepcopy(table_data)

# %%
online_data = w.get_online_data()

# %%
table_data = w.get_updated_table(online_data, table_data)

# %%
w.set_ymusic_likes(online_data, table_data)

# %%
if old_data:
    source.bulk_update(table_data, cached_old_data=old_data)
    print('Google sheets data updated')

# %%
if not old_data:
    table_data = TableHelper.sort(table_data)
    source.bulk_write(table_data)
    old_data = table_data

    print('Google sheets data was re/created with all current likes.')


