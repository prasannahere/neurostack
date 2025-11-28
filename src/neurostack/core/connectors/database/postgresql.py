"""
PostgreSQL Connector

This module provides a connector for PostgreSQL databases.
"""

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, Optional, List
import logging
from .base import BaseConnector

logger = logging.getLogger(__name__)


class PostgreSQLConnector(BaseConnector):
    """
    Connector for PostgreSQL databases.
    
    Configuration parameters:
        host: Database host (default: localhost)
        port: Database port (default: 5432)
        database: Database name (required)
        user: Database user (required)
        password: Database password (required)
        minconn: Minimum connections for connection pool (default: 1)
        maxconn: Maximum connections for connection pool (default: 10)
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
        Establish connection to PostgreSQL database.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 5432)
            database = self.config['database']
            user = self.config['user']
            password = self.config['password']
            minconn = self.config.get('minconn', 1)
            maxconn = self.config.get('maxconn', 10)
            
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=minconn,
                maxconn=maxconn,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
            
            # Test connection
            conn = self.connection_pool.getconn()
            self.connection_pool.putconn(conn)
            
            self._is_connected = True
            logger.info(f"Successfully connected to PostgreSQL database: {database}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Close the connection pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
            self._is_connected = False
            logger.info("Disconnected from PostgreSQL")
    
    def is_connected(self) -> bool:
        """Check if the connector is currently connected."""
        return self._is_connected and self.connection_pool is not None
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query on PostgreSQL.
        
        Args:
            query: SQL query string
            params: Optional dictionary of parameters for parameterized queries
            
        Returns:
            List of dictionaries containing query results
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to PostgreSQL database")
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Fetch results for SELECT queries
            if query.strip().upper().startswith('SELECT'):
                results = cursor.fetchall()
                return [dict(row) for row in results]
            else:
                # For INSERT, UPDATE, DELETE
                conn.commit()
                return [{'rows_affected': cursor.rowcount}]
                
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error executing query: {str(e)}")
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def health_check(self) -> bool:
        """
        Perform a health check on the PostgreSQL connection.
        
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

