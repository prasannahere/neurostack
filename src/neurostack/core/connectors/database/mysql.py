"""
MySQL Connector

This module provides a connector for MySQL databases.
"""

import mysql.connector
from mysql.connector import pooling, Error
from typing import Any, Dict, Optional, List
import logging
from .base import BaseConnector

logger = logging.getLogger(__name__)


class MySQLConnector(BaseConnector):
    """
    Connector for MySQL databases.
    
    Configuration parameters:
        host: Database host (default: localhost)
        port: Database port (default: 3306)
        database: Database name (required)
        user: Database user (required)
        password: Database password (required)
        pool_name: Connection pool name (default: mysql_pool)
        pool_size: Connection pool size (default: 5)
        autocommit: Enable autocommit (default: True)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_pool = None
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate required configuration parameters."""
        required = ['database', 'user', 'password']
        for param in required:
            if param not in self.config:
                raise ValueError(f"Missing required configuration parameter: {param}")
    
    def connect(self) -> bool:
        """
        Establish connection to MySQL database.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 3306)
            database = self.config['database']
            user = self.config['user']
            password = self.config['password']
            pool_name = self.config.get('pool_name', 'mysql_pool')
            pool_size = self.config.get('pool_size', 5)
            autocommit = self.config.get('autocommit', True)
            
            pool_config = {
                'pool_name': pool_name,
                'pool_size': pool_size,
                'pool_reset_session': True,
                'host': host,
                'port': port,
                'database': database,
                'user': user,
                'password': password,
                'autocommit': autocommit
            }
            
            self.connection_pool = pooling.MySQLConnectionPool(**pool_config)
            
            # Test connection
            conn = self.connection_pool.get_connection()
            conn.close()
            
            self._is_connected = True
            logger.info(f"Successfully connected to MySQL database: {database}")
            return True
            
        except Error as e:
            logger.error(f"Failed to connect to MySQL: {str(e)}")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MySQL: {str(e)}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Close all connections in the pool."""
        if self.connection_pool:
            # MySQL connection pool doesn't have a closeall method
            # Connections are closed when the pool is garbage collected
            # We can try to close all connections manually
            try:
                # Get all connections and close them
                for _ in range(self.connection_pool.pool_size):
                    try:
                        conn = self.connection_pool.get_connection()
                        conn.close()
                    except:
                        pass
            except:
                pass
            
            self._is_connected = False
            logger.info("Disconnected from MySQL")
    
    def is_connected(self) -> bool:
        """Check if the connector is currently connected."""
        if not self._is_connected or not self.connection_pool:
            return False
        
        try:
            # Test connection
            conn = self.connection_pool.get_connection()
            conn.close()
            return True
        except Exception:
            self._is_connected = False
            return False
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query on MySQL.
        
        Args:
            query: SQL query string
            params: Optional dictionary or tuple of parameters for parameterized queries
            
        Returns:
            List of dictionaries containing query results
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MySQL database")
        
        conn = None
        try:
            conn = self.connection_pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            if params:
                if isinstance(params, dict):
                    # Convert dict to tuple if needed, or use named parameters
                    cursor.execute(query, params)
                else:
                    cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Fetch results for SELECT queries
            if query.strip().upper().startswith('SELECT'):
                results = cursor.fetchall()
                return results if results else []
            else:
                # For INSERT, UPDATE, DELETE
                conn.commit()
                return [{'rows_affected': cursor.rowcount, 'lastrowid': cursor.lastrowid}]
                
        except Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Error executing query: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def health_check(self) -> bool:
        """
        Perform a health check on the MySQL connection.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            if not self.is_connected():
                return False
            
            result = self.execute_query("SELECT 1 as health_check")
            return len(result) > 0 and result[0].get('health_check') == 1
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

