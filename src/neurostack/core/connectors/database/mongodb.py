"""
MongoDB Connector

This module provides a connector for MongoDB databases.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Any, Dict, Optional, List
import logging
from .base import BaseConnector

logger = logging.getLogger(__name__)


class MongoDBConnector(BaseConnector):
    """
    Connector for MongoDB databases.
    
    Configuration parameters:
        host: Database host (default: localhost)
        port: Database port (default: 27017)
        database: Database name (required)
        username: Database username (optional)
        password: Database password (optional)
        auth_source: Authentication database (default: admin)
        connection_timeout: Connection timeout in ms (default: 5000)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self.db = None
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate required configuration parameters."""
        if 'database' not in self.config:
            raise ValueError("Missing required configuration parameter: database")
    
    def connect(self) -> bool:
        """
        Establish connection to MongoDB database.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 27017)
            database = self.config['database']
            username = self.config.get('username')
            password = self.config.get('password')
            auth_source = self.config.get('auth_source', 'admin')
            connection_timeout = self.config.get('connection_timeout', 5000)
            
            # Build connection string
            if username and password:
                connection_string = f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource={auth_source}"
            else:
                connection_string = f"mongodb://{host}:{port}/{database}"
            
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=connection_timeout
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            self.db = self.client[database]
            self._is_connected = True
            logger.info(f"Successfully connected to MongoDB database: {database}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {str(e)}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self._is_connected = False
            self.db = None
            logger.info("Disconnected from MongoDB")
    
    def is_connected(self) -> bool:
        """Check if the connector is currently connected."""
        if not self._is_connected or not self.client:
            return False
        
        try:
            # Quick check
            self.client.admin.command('ping')
            return True
        except Exception:
            self._is_connected = False
            return False
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a query on MongoDB.
        
        Args:
            query: Collection name (MongoDB doesn't use SQL)
            params: Dictionary containing:
                - operation: 'find', 'insert_one', 'insert_many', 'update_one', 
                           'update_many', 'delete_one', 'delete_many'
                - filter: Filter dictionary for find/update/delete operations
                - document: Document(s) for insert operations
                - update: Update dictionary for update operations
                - projection: Projection dictionary for find operations
                - limit: Limit for find operations
                - sort: Sort specification for find operations
                
        Returns:
            List of dictionaries containing query results
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MongoDB database")
        
        if not params:
            raise ValueError("MongoDB connector requires params dictionary with operation and other details")
        
        collection_name = query
        operation = params.get('operation', 'find')
        collection = self.db[collection_name]
        
        try:
            if operation == 'find':
                filter_dict = params.get('filter', {})
                projection = params.get('projection')
                limit = params.get('limit')
                sort = params.get('sort')
                
                cursor = collection.find(filter_dict, projection)
                if sort:
                    cursor = cursor.sort(sort)
                if limit:
                    cursor = cursor.limit(limit)
                
                return list(cursor)
                
            elif operation == 'insert_one':
                document = params.get('document')
                if not document:
                    raise ValueError("document parameter required for insert_one")
                result = collection.insert_one(document)
                return [{'inserted_id': str(result.inserted_id)}]
                
            elif operation == 'insert_many':
                documents = params.get('documents', [])
                if not documents:
                    raise ValueError("documents parameter required for insert_many")
                result = collection.insert_many(documents)
                return [{'inserted_ids': [str(id) for id in result.inserted_ids]}]
                
            elif operation == 'update_one':
                filter_dict = params.get('filter', {})
                update = params.get('update')
                if not update:
                    raise ValueError("update parameter required for update_one")
                result = collection.update_one(filter_dict, update)
                return [{'matched_count': result.matched_count, 'modified_count': result.modified_count}]
                
            elif operation == 'update_many':
                filter_dict = params.get('filter', {})
                update = params.get('update')
                if not update:
                    raise ValueError("update parameter required for update_many")
                result = collection.update_many(filter_dict, update)
                return [{'matched_count': result.matched_count, 'modified_count': result.modified_count}]
                
            elif operation == 'delete_one':
                filter_dict = params.get('filter', {})
                result = collection.delete_one(filter_dict)
                return [{'deleted_count': result.deleted_count}]
                
            elif operation == 'delete_many':
                filter_dict = params.get('filter', {})
                result = collection.delete_many(filter_dict)
                return [{'deleted_count': result.deleted_count}]
                
            else:
                raise ValueError(f"Unsupported operation: {operation}")
                
        except Exception as e:
            logger.error(f"Error executing MongoDB operation: {str(e)}")
            raise
    
    def health_check(self) -> bool:
        """
        Perform a health check on the MongoDB connection.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            if not self.is_connected():
                return False
            
            # Ping the database
            self.client.admin.command('ping')
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

