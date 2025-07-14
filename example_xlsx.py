# %%
import logging
from copy import deepcopy
from liketable import Liketable
from table_helper import TableHelper
from source_xlsx import XlsxSource

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# %%
source = XlsxSource(filename='./changes.xlsx')

w = Liketable(token=open('token.txt').read().strip('\n'), language='en')

# %%
table_data = source.bulk_read()

old_data = deepcopy(table_data)

# %%
online_data = w.get_online_data()

# %%
table_data = w.get_updated_table(online_data, table_data)

# %%
w.upload_changed_likes(online_data, table_data)

# %%
if old_data:
    source.bulk_update(table_data, cached_old_data=old_data)
    print('XLSX file updated')

# %%
if not old_data:
    table_data = TableHelper.sort(table_data)
    source.bulk_write(table_data)
    old_data = table_data

    print('XLSX file was re/created with all current likes.')


