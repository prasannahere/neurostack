import boto3
from botocore.exceptions import ClientError
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from .base import BaseSourceConnector
import os

class S3Connector(BaseSourceConnector):
    """
    AWS S3 connector.
    """

    def __init__(self, config: Dict[str, Any], credentials: Optional[Dict[str, Any]] = None, metadataStore=None):
        super().__init__(config, credentials, metadataStore)
        if "bucket_name" not in self.config:
            raise ValueError("Missing required configuration parameter: bucket_name")
        self.s3 = None
        self.bucket = None

    def connect(self) -> bool:
        """Establish connection to AWS S3."""
        try:
            params = {}
            if "aws_access_key_id" in self.config:
                params["aws_access_key_id"] = self.config["aws_access_key_id"]
            if "aws_secret_access_key" in self.config:
                params["aws_secret_access_key"] = self.config["aws_secret_access_key"]
            if "region_name" in self.config:
                params["region_name"] = self.config["region_name"]
            
            self.s3 = boto3.client("s3", **params)
            self.bucket = self.config["bucket_name"]
            self.s3.head_bucket(Bucket=self.bucket)
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise

    def disconnect(self) -> None:
        """Close the S3 connection."""
        self._connected = False
        self.s3 = None
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
        paginator = self.s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
        
        for page in pages:
            for item in page.get("Contents", []):
                last_modified = item["LastModified"]
                if last_modified.tzinfo is None:
                    last_modified = last_modified.replace(tzinfo=timezone.utc)
                if last_modified > cutoff:
                    results.append({
                        "key": item["Key"],
                        "name": item["Key"].split("/")[-1],
                        "last_modified": last_modified.isoformat(),
                        "size": item["Size"]
                    })
        
        return results

    def consolidate_metadata(self, source_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert S3 metadata to match the Pydantic Metadata schema.
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
        Download files from S3 into the given destination folder.
        """
        os.makedirs(destination, exist_ok=True)
        
        for file_meta in files:
            key = file_meta["key"]
            original_name = file_meta["name"]
            local_path = os.path.join(destination, os.path.basename(original_name))
            
            try:
                self.s3.download_file(self.bucket, key, local_path)
                print(f"Downloaded '{original_name}' to '{local_path}'")
            except ClientError as e:
                print(f"Error downloading '{original_name}': {e}")
                raise
