from google.cloud import storage
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from .base import BaseSourceConnector
import os

class GCSConnector(BaseSourceConnector):
    """
    Google Cloud Storage connector.
    """

    def __init__(self, config: Dict[str, Any], credentials: Optional[Dict[str, Any]] = None, metadataStore=None):
        super().__init__(config, credentials, metadataStore)
        if 'bucket_name' not in self.config:
            raise ValueError("Missing required configuration parameter: bucket_name")
        self.client = None
        self.bucket = None

    def connect(self) -> bool:
        """Establish connection to Google Cloud Storage."""
        try:
            credentials_path = self.config.get('credentials_path')
            project = self.config.get('project')
            
            if credentials_path:
                self.client = storage.Client.from_service_account_json(
                    credentials_path,
                    project=project
                )
            else:
                self.client = storage.Client(project=project)
            
            self.bucket = self.client.bucket(self.config['bucket_name'])
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise

    def disconnect(self) -> None:
        """Close the GCS connection."""
        self._connected = False
        self.client = None
        self.bucket = None

    def list_source_files(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetch files modified after 'cutoff' (datetime) and optionally filter by prefix.
        """
        cutoff: datetime = filters.get("cutoff", datetime(1970, 1, 1, tzinfo=timezone.utc))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        prefix = filters.get("prefix", "")
        
        results = []
        blobs = self.bucket.list_blobs(prefix=prefix)
        
        for blob in blobs:
            if blob.time_created:
                time_created = blob.time_created
                if time_created.tzinfo is None:
                    time_created = time_created.replace(tzinfo=timezone.utc)
                if time_created > cutoff:
                    results.append({
                        "key": blob.name,
                        "name": blob.name.split('/')[-1],
                        "last_modified": blob.time_created.isoformat(),
                        "size": blob.size
                    })
        
        return results

    def consolidate_metadata(self, source_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert GCS metadata to match the Pydantic Metadata schema.
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
        Download files from GCS into the given destination folder.
        """
        os.makedirs(destination, exist_ok=True)
        
        for file_meta in files:
            key = file_meta["key"]
            original_name = file_meta["name"]
            local_path = os.path.join(destination, os.path.basename(original_name))
            
            blob = self.bucket.blob(key)
            blob.download_to_filename(local_path)
            print(f"Downloaded '{original_name}' to '{local_path}'")
