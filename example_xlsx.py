# %%
import logging
from ymusic_liketable import Worker
from driver_xlsx import XlsxFileDriver

logging.basicConfig(
    level=logging.WARN,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# %%
table_driver = XlsxFileDriver(filename='./changes.xlsx')

w = Worker(token=open('token.txt').read().strip('\n'), language='en')

# %%
try:
    table_data = table_driver.bulk_read()
except FileNotFoundError:
    print("File not found, starting with empty changes list.")
    table_data = []

# %%
online_data = w.get_online_data()

# %%
table_data = w.get_updated_table(online_data, table_data)

# %%
w.set_ymusic_likes(online_data, table_data)

# %%
table_driver.bulk_write(table_data)
print('Table file saved')