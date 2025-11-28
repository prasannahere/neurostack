"""
Data Storage Connectors Package

This package provides connectors for popular data storage systems:

Database Connectors:
- PostgreSQL
- MongoDB
- Redis
- MySQL

File Storage Connectors:
- AWS S3
- Google Cloud Storage
- Azure Blob Storage
- Google Drive
- Dropbox
"""

# Use lazy imports to avoid requiring all dependencies when importing from submodules
def __getattr__(name):
    """Lazy import connectors only when accessed."""
    if name in {
        'BaseConnector',
        'PostgreSQLConnector',
        'MongoDBConnector',
        'RedisConnector',
        'MySQLConnector'
    }:
        from .database import (
            BaseConnector,
            PostgreSQLConnector,
            MongoDBConnector,
            RedisConnector,
            MySQLConnector
        )
        return locals()[name]
    
    if name in {
        'BaseFileStorageConnector',
        'S3Connector',
        'GCSConnector',
        'AzureBlobConnector',
        'GoogleDriveConnector',
        'DropboxConnector'
    }:
        from .remote import (
            BaseFileStorageConnector,
            S3Connector,
            GCSConnector,
            AzureBlobConnector,
            GoogleDriveConnector,
            DropboxConnector
        )
        return locals()[name]
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    # Database
    'BaseConnector',
    'PostgreSQLConnector',
    'MongoDBConnector',
    'RedisConnector',
    'MySQLConnector',
    # File Storage
    'BaseFileStorageConnector',
    'S3Connector',
    'GCSConnector',
    'AzureBlobConnector',
    'GoogleDriveConnector',
    'DropboxConnector',
]

__version__ = '1.0.0'

