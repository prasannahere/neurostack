from azure.storage.blob import BlobServiceClient
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from .base import BaseSourceConnector
import os

class AzureBlobConnector(BaseSourceConnector):
    """
    Azure Blob Storage connector.
    """

    def __init__(self, config: Dict[str, Any], credentials: Optional[Dict[str, Any]] = None, metadataStore=None):
        super().__init__(config, credentials, metadataStore)
        if 'connection_string' not in self.config:
            required = ['account_name', 'account_key', 'container_name']
            for param in required:
                if param not in self.config:
                    raise ValueError(f"Missing required configuration parameter: {param}")
        self.service = None

    def connect(self) -> bool:
        """Establish connection to Azure Blob Storage."""
        try:
            if 'connection_string' in self.config:
                container_name = self.config.get('container_name', '')
                if not container_name:
                    raise ValueError("container_name is required even when using connection_string")
                blob_service_client = BlobServiceClient.from_connection_string(
                    self.config['connection_string']
                )
            else:
                account_name = self.config['account_name']
                account_key = self.config['account_key']
                blob_url = f"https://{account_name}.blob.core.windows.net"
                blob_service_client = BlobServiceClient(
                    account_url=blob_url,
                    credential=account_key
                )
            
            container_name = self.config.get('container_name', '')
            self.service = blob_service_client.get_container_client(container_name)
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise

    def disconnect(self) -> None:
        """Close the Azure Blob Storage connection."""
        self._connected = False
        self.service = None

    def list_source_files(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetch files modified after 'cutoff' (datetime) and optionally filter by prefix.
        """
        cutoff: datetime = filters.get("cutoff", datetime(1970, 1, 1, tzinfo=timezone.utc))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        prefix = filters.get("prefix", "")
        
        results = []
        blobs = self.service.list_blobs(name_starts_with=prefix)
        
        for blob in blobs:
            if blob.last_modified:
                last_modified = blob.last_modified
                if last_modified.tzinfo is None:
                    last_modified = last_modified.replace(tzinfo=timezone.utc)
                if last_modified > cutoff:
                    results.append({
                        "key": blob.name,
                        "name": blob.name.split('/')[-1],
                        "last_modified": blob.last_modified.isoformat(),
                        "size": blob.size
                    })
        
        return results

    def consolidate_metadata(self, source_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert Azure Blob metadata to match the Pydantic Metadata schema.
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
        Download files from Azure Blob Storage into the given destination folder.
        """
        os.makedirs(destination, exist_ok=True)
        
        for file_meta in files:
            key = file_meta["key"]
            original_name = file_meta["name"]
            local_path = os.path.join(destination, os.path.basename(original_name))
            
            blob_client = self.service.get_blob_client(key)
            with open(local_path, "wb") as f:
                stream = blob_client.download_blob()
                f.write(stream.readall())
            
            print(f"Downloaded '{original_name}' to '{local_path}'")
