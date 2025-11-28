from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from typing import Any, Dict, List
from datetime import datetime, timezone
from .base import BaseSourceConnector
import os
from googleapiclient.http import MediaIoBaseDownload

class GoogleDriveConnector(BaseSourceConnector):
    """
    Google Drive connector using immediate parent check only.
    """

    def __init__(self, config: Dict[str, Any], credentials: Dict[str, Any], metadataStore=None):
        super().__init__(config, credentials, metadataStore)
        self.service = None
        self.target_folder_id = config.get("folderId") 

    def connect(self) -> bool:
        creds = Credentials.from_service_account_info(self.credentials, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        self.service = build('drive', 'v3', credentials=creds)
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self.service = None

    def list_source_files(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetch files modified after 'cutoff' (datetime) and optionally filter by immediate parent.
        """
        cutoff: datetime = filters.get("cutoff", datetime(1970,1,1, tzinfo=timezone.utc))
        # Google Drive API expects RFC 3339 format: YYYY-MM-DDTHH:MM:SS.mmmZ
        # Convert datetime to RFC 3339 format
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        query = f"modifiedTime > '{cutoff_str}' and trashed=false"

        if self.target_folder_id:
            query += f" and '{self.target_folder_id}' in parents"

        print(f"Debug: Query = {query}")
        results = []
        page_token = None

        while True:
            try:
                response = self.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, parents, size, modifiedTime, mimeType)",
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()

                files = response.get("files", [])
                print(f"Debug: Found {len(files)} files in this page")
                
                for f in files:
                    results.append({
                        "key": f["id"],  # file id as unique key
                        "name": f["name"],
                        "last_modified": f["modifiedTime"],
                        "size": int(f.get("size", 0)),
                        "parents": f.get("parents", [])
                    })

                page_token = response.get("nextPageToken", None)
                if not page_token:
                    break
            except Exception as e:
                print(f"Error querying Google Drive: {e}")
                raise

        print(f"Debug: Total files found: {len(results)}")
        return results

    def consolidate_metadata(self, source_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert Google Drive metadata to match the Pydantic Metadata schema.
        Converts last_modified from ISO string to datetime object.
        """
        consolidated = {}
        for file in source_files:
            # Parse ISO format datetime string to datetime object
            last_modified_str = file["last_modified"]
            if isinstance(last_modified_str, str):
                last_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
            else:
                last_modified = last_modified_str
            
            consolidated[file["key"]] = {
                "key": file["key"],
                "name": file["name"],
                "size": file["size"],
                "last_modified": last_modified
            }
        return consolidated

    def fetch_one_by_one(self, files: List[Dict[str, Any]], destination: str) -> None:
        """
        Download files from Google Drive into the given destination folder.

        Args:
            files: List of dictionaries, each with keys "key" (Google Drive fileId) and "name" (original filename)
            destination: Local folder path where the files will be saved
        """
        # Ensure the destination folder exists
        os.makedirs(destination, exist_ok=True)

        for file_meta in files:
            file_id = file_meta["key"]
            original_name = file_meta["name"]

            # Construct full local path
            local_path = os.path.join(destination, os.path.basename(original_name))

            # Prepare download request
            request = self.service.files().get_media(fileId=file_id)
            with open(local_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

            print(f"Downloaded '{original_name}' to '{local_path}'")
