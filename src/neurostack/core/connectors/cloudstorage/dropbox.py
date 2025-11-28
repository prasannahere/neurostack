import dropbox
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from .base import BaseSourceConnector
import os

class DropboxConnector(BaseSourceConnector):
    """
    Dropbox connector.
    """

    def __init__(self, config: Dict[str, Any], credentials: Optional[Dict[str, Any]] = None, metadataStore=None):
        super().__init__(config, credentials, metadataStore)
        if 'access_token' not in self.config:
            raise ValueError("Missing required configuration parameter: access_token")
        self.dbx = None

    def connect(self) -> bool:
        """Establish connection to Dropbox."""
        try:
            self.dbx = dropbox.Dropbox(self.config['access_token'])
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise

    def disconnect(self) -> None:
        """Close the Dropbox connection."""
        self._connected = False
        self.dbx = None

    def list_source_files(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetch files modified after 'cutoff' (datetime) and optionally filter by prefix.
        """
        cutoff: datetime = filters.get("cutoff", datetime(1970, 1, 1, tzinfo=timezone.utc))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        prefix = filters.get("prefix", "")
        
        if prefix and not prefix.startswith('/'):
            prefix = '/' + prefix
        elif not prefix:
            prefix = ''
        
        results = []
        result = self.dbx.files_list_folder(path=prefix if prefix else '', recursive=True)
        
        while True:
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    if entry.server_modified:
                        server_modified = entry.server_modified
                        if server_modified.tzinfo is None:
                            server_modified = server_modified.replace(tzinfo=timezone.utc)
                        if server_modified > cutoff:
                            results.append({
                                "key": entry.path_display,
                                "name": entry.name,
                                "last_modified": entry.server_modified.isoformat(),
                                "size": entry.size
                            })
            
            if not result.has_more:
                break
            
            result = self.dbx.files_list_folder_continue(result.cursor)
        
        return results

    def consolidate_metadata(self, source_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert Dropbox metadata to match the Pydantic Metadata schema.
        Converts last_modified from ISO string to datetime object.
        """
        consolidated = {}
        for file in source_files:
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
        Download files from Dropbox into the given destination folder.
        """
        os.makedirs(destination, exist_ok=True)
        
        for file_meta in files:
            key = file_meta["key"]
            original_name = file_meta["name"]
            local_path = os.path.join(destination, os.path.basename(original_name))
            
            if not key.startswith('/'):
                key = '/' + key
            
            _, response = self.dbx.files_download(key)
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            print(f"Downloaded '{original_name}' to '{local_path}'")
