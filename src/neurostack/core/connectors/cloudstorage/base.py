from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import sqlite3
import logging

"""
Base File Storage Connector Class

This module provides the abstract base class for all file storage connectors.
"""


logger = logging.getLogger(__name__)



# Pydantic model
class Metadata(BaseModel):
    key: str
    name: str
    size: int
    last_modified: datetime

    class Config:
        from_attributes = True


class SQLiteMetadataStore:
    """SQLite store mapping each Pydantic field to a column."""

    def __init__(self, db_path: str = "./dst_metadata.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                last_modified TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def get(self, key: str) -> Optional[Metadata]:
        cursor = self.conn.execute(
            "SELECT key, name, size, last_modified FROM metadata WHERE key=?;",
            (key,)
        )
        row = cursor.fetchone()
        if row:
            return Metadata(
                key=row[0],
                name=row[1],
                size=row[2],
                last_modified=datetime.fromisoformat(row[3])
            )
        return None

    def put(self, metadata: Metadata) -> None:
        self.conn.execute("""
            INSERT OR REPLACE INTO metadata (key, name, size, last_modified)
            VALUES (?, ?, ?, ?);
        """, (
            metadata.key,
            metadata.name,
            metadata.size,
            metadata.last_modified.isoformat()
        ))
        self.conn.commit()

    def delete(self, key: str) -> None:
        self.conn.execute(
            "DELETE FROM metadata WHERE key=?;",
            (key,)
        )
        self.conn.commit()


class BaseSourceConnector(ABC):

    def __init__(self, config: Dict[str, Any], credentials: Optional[Dict[str, Any]] = None, metadataStore: Optional[SQLiteMetadataStore] = None):
        self.config = config
        self._connected = False
        self.metadataStore = metadataStore or SQLiteMetadataStore('./dst_metadata.db')
        self.credentials = credentials or {}


    # ---------- CONNECTION ----------
    @abstractmethod
    def connect(self) -> bool:
        self._connected = True
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        self._connected = False
        raise NotImplementedError

    def is_connected(self) -> bool:
        return self._connected

    # ---------- FETCH OPERATIONS ----------
    @abstractmethod
    def list_source_files(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Must return list of source metadata dicts:
        [
          {"key": "...", "last_modified": ..., "size": ...},
          ...
        ]
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_one_by_one(self, files: List[Dict[str, Any]], destination: str) -> None:
        """
        Download each file in the provided list to the destination folder.
        """
        raise NotImplementedError
    
    def _put_metadata(self, metadata: Metadata) -> None:
        self.metadataStore.put(metadata)

    @abstractmethod
    def consolidate_metadata(self, source_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        raise NotImplementedError
    # duplicate removal logic
    def _remove_duplicates(self, source_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove files already present in destination.
        dst_metadata = { key: { "last_modified": ..., "size": ... } }
        """
        if not source_files:
            return []
        
        source_keys = [file["key"] for file in source_files]
        placeholders = ",".join("?" * len(source_keys))
        
        cursor = self.metadataStore.conn.execute(
            f"SELECT key FROM metadata WHERE key IN ({placeholders});",
            source_keys
        )
        existing_keys = {row[0] for row in cursor.fetchall()}
        
        metadata_of_unique_files = [
            file for file in source_files 
            if file["key"] not in existing_keys
        ]

        return metadata_of_unique_files

    # public method orchestrating all
    def fetch(self, filters: Dict[str, Any], Destination : str):
        """
        Gets Dict as filters, must be compatible!
        source files return the metadata set to download
        remove duplicates prepares final files to download
        fetch one by one downloads the files to the local path and receive the exact links to download
        """

        if not self._connected:
            raise RuntimeError("Connector is not connected.")

        source_files = self.list_source_files(filters)
        files_to_download = self._remove_duplicates(source_files)

        print(files_to_download)

        self.fetch_one_by_one(files_to_download, Destination)

        consolidated = self.consolidate_metadata(files_to_download)
        for key, metadata_dict in consolidated.items():
            metadata = Metadata(**metadata_dict)
            self._put_metadata(metadata)

        return files_to_download

    # ---------- CONTEXT MANAGER ----------
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def __repr__(self):
        return f"{self.__class__.__name__}(connected={self._connected})"

