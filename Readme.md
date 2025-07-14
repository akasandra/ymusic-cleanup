# ymusic-liketable

Скрипт для получения таблицы со всеми лайками на музыку. Если снимать галочки в таблице, лайки будут сняты и это позволяет управлять рекомендациями "волны", например.

Позволяет точнее настроить работу рекомендаций/vibe, убрать много лайков за раз

### Использование

 1. Получить токен из браузера https://github.com/MarshalX/yandex-music-api/discussions/513. Сохранить в `token.txt`
 3. Зависимости 
      `poetry install --no-root`
 4. Выполнение
      `poetry run python example_xlsx.py`
 7. Снять ненужные лайки, сортируя треки по жанрам, году, названию, времени лайка и т.д.
 9. Перезапуск скрипта обновит лайки -- снимет или поставит обратно.

Если новый лайк поставлен в приложении, но его нет в файле, он добавляется в файл. Если ранее он был снят вручную, в таблице будет снова поставлен.

Если лайк снят в приложении, это будет отражено в таблице. В том числе пустым timestamp.

**Example**: `example_xlsx.py`

#### Google Sheets API
You may use Google Sheets API to work on google cloud spreadsheet document. 

Requirements:

 - Ath for google API (`creds.json`): Service Account (personal use) or OAuth (many users/apps mode)
 - A spreadsheet document (href for `table_url`) with access shared to `client_email` (creds) 

 **Example**: `example_google.py`

##### Set up access

1. Google Console Project
2. Enable [Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com) per project
3. Create Credentials and download JSON file (as `creds.json`)