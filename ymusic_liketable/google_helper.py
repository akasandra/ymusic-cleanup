import gspread
import json
from typing import List, Union, Dict, Callable
from google.oauth2.credentials import Credentials

class GoogleHelper:

    @classmethod
    def client_service_account(cls, credentials_source: Union[str, Dict]) -> gspread.Client:
        """
        Authorize gspread client using a service account.

        Args:
            credentials_source: Path to service account JSON file or dict with credentials.

        Returns:
            gspread.Client authorized with service account.
        """
        if isinstance(credentials_source, str):
            gc = gspread.service_account(filename=credentials_source)
        else:
            gc = gspread.service_account_from_dict(credentials_source)
        return gc

    @classmethod
    def client_oauth(
        cls,
        token_info: dict,
        client_id: str,
        client_secret: str,
        scopes: list = None
    ) -> gspread.Client:
        """
        Authorize gspread client using OAuth2 tokens with refresh support.

        Args:
            token_info: Dict containing 'token', 'refresh_token', 'token_uri', etc.
            client_id: OAuth client ID.
            client_secret: OAuth client secret.
            scopes: List of OAuth scopes (default to Sheets and Drive).

        Returns:
            gspread.Client authorized with OAuth2 credentials.
        """
        if scopes is None:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

        creds = Credentials(
            token=token_info.get('token'),
            refresh_token=token_info.get('refresh_token'),
            token_uri=token_info.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes
        )

        gc = gspread.Client(auth=creds)
        gc.session = gspread.Client(auth=creds).session  # ensure session is set
        return gc

    @classmethod
    def client_json_creds(
        cls,
        filename: str,
        client_id: str = None,
        client_secret: str = None,
        scopes: list = None
    ) -> gspread.Client:
        """
        Load credentials JSON file, detect type, and return authorized gspread client.

        Args:
            filename: Path to JSON credentials file (service account or OAuth).
            client_id: OAuth client ID (required for OAuth).
            client_secret: OAuth client secret (required for OAuth).
            scopes: OAuth scopes (optional).

        Returns:
            Authorized gspread.Client instance.
        """
        with open(filename, 'r') as f:
            creds_json = json.load(f)

        cred_type = creds_json.get('type')

        if cred_type == 'service_account':
            return cls.client_service_account(creds_json)
        elif cred_type == 'authorized_user':
            # OAuth token info expected in creds_json
            if client_id is None or client_secret is None:
                raise ValueError("client_id and client_secret are required for OAuth authorization")
            token_info = {
                'token': creds_json.get('token'),
                'refresh_token': creds_json.get('refresh_token'),
                'token_uri': creds_json.get('token_uri', 'https://oauth2.googleapis.com/token')
            }
            return cls.client_oauth(token_info, client_id, client_secret, scopes)
        else:
            raise ValueError(f"Unsupported credential type: {cred_type}")

    @classmethod
    def make_file_update_function(cls, filename: Union[str, None]) -> Union[Callable[[Credentials], None], None]:
        """
        Generates a callback to rewrite credentials (refresh token) to a file if refresh token has changed.

        For OAuth mode, refresh token in login credentials may change over time.
        Before each API call it is tested if needs to refresh and if so, it gets refresh.
        If it does, GoogleSheetSource will need a callback to call to update the credentials.

        Args:
            filename: path to JSON file. If None, None is returned.

        Returns:
            closure that reads creds from file, updates refreshtoken and writes credentials back to the file.
            if no filename provided, returns None.
        """
        if not filename:
            return None
        
        def refreshtoken_writer_perform(creds: Credentials):
            # Load existing credentials JSON
            with open(filename, 'r') as f:
                creds_json = json.load(f)

            # Only rewrite token if it is used
            old_refresh_token = creds_json.get('refresh_token')
            new_refresh_token = creds.refresh_token

            if new_refresh_token and new_refresh_token != old_refresh_token:
                creds_json['refresh_token'] = new_refresh_token
                creds_json['token'] = creds.token
                creds_json['token_uri'] = creds.token_uri

                with open(filename, 'w') as f:
                    json.dump(creds_json, f, indent=2)

        return refreshtoken_writer_perform

# End