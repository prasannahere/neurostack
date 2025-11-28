"""
Network Filesystem Connector

This module provides a connector for network file systems (SMB/CIFS and NFS).
Files are downloaded from the network share to a local directory.
"""

import os
from typing import Any, Dict, BinaryIO
import logging

try:
    from smbclient import open_file, listdir, stat, register_session, isdir
    from smbclient.path import exists as smb_exists
    SMB_AVAILABLE = True
except ImportError:
    SMB_AVAILABLE = False

from .base import BaseFilesystemConnector

logger = logging.getLogger(__name__)


class NetworkFilesystemConnector(BaseFilesystemConnector):
    """
    Connector for network file systems (SMB/CIFS and NFS).
    
    Supports:
    - SMB/CIFS shares (using smbprotocol)
    - NFS shares (mounted or mountable)
    
    Configuration parameters:
        protocol: 'smb' or 'nfs' (required)
        share_path: Network share path (required)
            - For SMB: '\\\\server\\share' or '//server/share'
            - For NFS: '/mnt/nfs' or 'server:/export'
        username: Username for SMB authentication (required for SMB)
        password: Password for SMB authentication (required for SMB)
        domain: Domain for SMB authentication (optional)
        local_directory: Local directory for downloads (required for downloadAll)
        metadata_file: Path to metadata store file (optional, defaults to .metadata.json in local_directory)
        source_path: Path within the share to sync (optional, defaults to root)
        recursive: Whether to recursively list files (default: True)
    """
    
    def __init__(self, config: Dict[str, Any]):
        # Validate required parameters before calling super
        if 'protocol' not in config:
            raise ValueError("Missing required configuration parameter: protocol (must be 'smb' or 'nfs')")
        
        if 'share_path' not in config:
            raise ValueError("Missing required configuration parameter: share_path")
        
        super().__init__(config)
        
        self.protocol = self.config['protocol'].lower()
        if self.protocol not in ['smb', 'nfs']:
            raise ValueError(f"Unsupported protocol: {self.protocol}. Must be 'smb' or 'nfs'")
        
        if self.protocol == 'smb' and not SMB_AVAILABLE:
            raise ImportError("smbprotocol library is required for SMB support. Install with: pip install smbprotocol")
        
        self.username = self.config.get('username')
        self.password = self.config.get('password')
        self.domain = self.config.get('domain')
        
        self._smb_session_registered = False
    
    def connect(self) -> bool:
        """Establish connection to the network filesystem."""
        try:
            if self.protocol == 'smb':
                return self._connect_smb()
            elif self.protocol == 'nfs':
                return self._connect_nfs()
        except Exception as e:
            logger.error(f"Failed to connect to network filesystem: {str(e)}")
            self._is_connected = False
            return False
    
    def _connect_smb(self) -> bool:
        """Connect to SMB/CIFS share."""
        if not SMB_AVAILABLE:
            raise ImportError("smbprotocol library is required for SMB support")
        
        try:
            # Register SMB session
            server = self._extract_smb_server()
            if self.username and self.password:
                register_session(
                    server=server,
                    username=self.username,
                    password=self.password,
                    domain=self.domain
                )
                self._smb_session_registered = True
                logger.info(f"Registered SMB session for {server}")
            
            # Verify connection by checking if share exists
            test_path = self._get_base_path()
            
            if not smb_exists(test_path):
                logger.warning(f"Share path does not exist or is not accessible: {test_path}")
            
            self._is_connected = True
            self.service = True  # Mark service as available
            logger.info(f"Successfully connected to SMB share: {self.share_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to SMB share: {str(e)}")
            self._is_connected = False
            return False
    
    def _connect_nfs(self) -> bool:
        """Connect to NFS share (verify mount point exists)."""
        try:
            # For NFS, we assume the share is already mounted
            # If it's not mounted, the user should mount it first
            test_path = self._get_base_path()
            
            if not os.path.exists(test_path):
                logger.warning(f"NFS path does not exist or is not mounted: {test_path}")
                logger.warning("Please ensure the NFS share is mounted before using this connector")
            
            self._is_connected = True
            self.service = True  # Mark service as available
            logger.info(f"Successfully connected to NFS share: {self.share_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to NFS share: {str(e)}")
            self._is_connected = False
            return False
    
    def _extract_smb_server(self) -> str:
        """Extract server name from SMB share path."""
        # Handle both \\server\share and //server/share formats
        path = self.share_path.replace('\\', '/')
        if path.startswith('//'):
            path = path[2:]
        parts = path.split('/')
        return parts[0] if parts else 'localhost'
    
    def disconnect(self) -> None:
        """Close the connection."""
        # For SMB, we could close the session, but smbclient manages this
        self._is_connected = False
        self.service = None
        self._smb_session_registered = False
    
    # -----------------------------------------
    # PROTOCOL-SPECIFIC IMPLEMENTATIONS
    # -----------------------------------------
    
    def _list_directory(self, path: str) -> list:
        """List items in a directory."""
        if self.protocol == 'smb':
            return list(listdir(path))
        else:
            return os.listdir(path)
    
    def _is_directory(self, path: str) -> bool:
        """Check if a path is a directory."""
        if self.protocol == 'smb':
            return isdir(path)
        else:
            return os.path.isdir(path)
    
    def _get_file_stat(self, path: str) -> Any:
        """Get file statistics."""
        if self.protocol == 'smb':
            return stat(path)
        else:
            return os.stat(path)
    
    def _open_file(self, path: str, mode: str = 'rb') -> BinaryIO:
        """Open a file for reading."""
        if self.protocol == 'smb':
            return open_file(path, mode=mode)
        else:
            return open(path, mode)
    
    def _path_exists(self, path: str) -> bool:
        """Check if a path exists."""
        if self.protocol == 'smb':
            return smb_exists(path)
        else:
            return os.path.exists(path)

