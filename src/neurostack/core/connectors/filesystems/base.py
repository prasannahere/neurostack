"""
Base Filesystem Connector Class

This module provides the abstract base class for all filesystem connectors.
"""

import os
import hashlib
from abc import abstractmethod
from typing import Any, Dict, List, BinaryIO
import logging
from datetime import datetime

from ..remote.base import BaseFileStorageConnector

logger = logging.getLogger(__name__)


class BaseFilesystemConnector(BaseFileStorageConnector):
    """
    Base class for filesystem connectors.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.share_path = self.config.get('share_path', '')
        self.source_path = self.config.get('source_path', '')
        self.recursive = self.config.get('recursive', True)
        self.service = None
    
    # -----------------------------------------
    # ABSTRACT METHODS
    # -----------------------------------------
    
    @abstractmethod
    def _list_directory(self, path: str) -> List[str]:
        raise NotImplementedError
    
    @abstractmethod
    def _is_directory(self, path: str) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def _get_file_stat(self, path: str) -> Any:
        raise NotImplementedError
    
    @abstractmethod
    def _open_file(self, path: str, mode: str = 'rb') -> BinaryIO:
        raise NotImplementedError
    
    @abstractmethod
    def _path_exists(self, path: str) -> bool:
        raise NotImplementedError
    
    def _get_base_path(self) -> str:
        if self.source_path:
            return os.path.join(self.share_path, self.source_path)
        return self.share_path
    
    # -----------------------------------------
    # CONTRACT METHODS
    # -----------------------------------------
    
    def listFiles(self, **kwargs) -> List[Dict[str, Any]]:
        self._ensureConnected()
        files = []
        base_path = self.source_path if self.source_path else ''
        full_path = os.path.join(self.share_path, base_path) if base_path else self.share_path
        
        try:
            items = self._list_directory(full_path)
            for item in items:
                item_path = os.path.join(full_path, item)
                rel_path = os.path.join(base_path, item) if base_path else item
                
                try:
                    if self._is_directory(item_path):
                        if self.recursive:
                            files.extend(self._list_files_recursive(rel_path))
                    else:
                        files.append({
                            'id': rel_path.replace('\\', '/'),
                            'name': item,
                            'path': rel_path.replace('\\', '/')
                        })
                except Exception as e:
                    logger.warning(f"Error accessing {item_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error listing directory {full_path}: {str(e)}")
        
        return files
    
    def getMetadata(self, file_id: str, **kwargs) -> Dict[str, Any]:
        self._ensureConnected()
        full_path = os.path.join(self.share_path, file_id)
        file_stat = self._get_file_stat(full_path)
        mtime = file_stat.st_mtime
        size = file_stat.st_size
        checksum = hashlib.md5(f"{file_id}:{mtime}:{size}".encode()).hexdigest()
        
        return {
            'id': file_id,
            'name': os.path.basename(file_id),
            'last_modified': datetime.fromtimestamp(mtime).isoformat(),
            'size': size,
            'checksum': checksum
        }
    
    def streamDownload(self, file_id: str, output_stream: BinaryIO, **kwargs) -> None:
        self._ensureConnected()
        full_path = os.path.join(self.share_path, file_id)
        
        with self._open_file(full_path, mode='rb') as file_handle:
            while True:
                chunk = file_handle.read(1024 * 1024)
                if not chunk:
                    break
                output_stream.write(chunk)
    
    def _list_files_recursive(self, base_path: str) -> List[Dict[str, Any]]:
        files = []
        full_path = os.path.join(self.share_path, base_path)
        
        try:
            items = self._list_directory(full_path)
            for item in items:
                item_path = os.path.join(full_path, item)
                rel_path = os.path.join(base_path, item)
                
                try:
                    if self._is_directory(item_path):
                        if self.recursive:
                            files.extend(self._list_files_recursive(rel_path))
                    else:
                        files.append({
                            'id': rel_path.replace('\\', '/'),
                            'name': item,
                            'path': rel_path.replace('\\', '/')
                        })
                except Exception as e:
                    logger.warning(f"Error accessing {item_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error listing directory {full_path}: {str(e)}")
        
        return files

