"""
Redis Connector

This module provides a connector for Redis databases.
"""

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from typing import Any, Dict, Optional, List
import logging
from .base import BaseConnector

logger = logging.getLogger(__name__)


class RedisConnector(BaseConnector):
    """
    Connector for Redis databases.
    
    Configuration parameters:
        host: Redis host (default: localhost)
        port: Redis port (default: 6379)
        db: Database number (default: 0)
        password: Redis password (optional)
        decode_responses: Decode responses as strings (default: True)
        socket_timeout: Socket timeout in seconds (default: 5)
        socket_connect_timeout: Socket connect timeout in seconds (default: 5)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
    
    def connect(self) -> bool:
        """
        Establish connection to Redis database.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 6379)
            db = self.config.get('db', 0)
            password = self.config.get('password')
            decode_responses = self.config.get('decode_responses', True)
            socket_timeout = self.config.get('socket_timeout', 5)
            socket_connect_timeout = self.config.get('socket_connect_timeout', 5)
            
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout
            )
            
            # Test connection
            self.client.ping()
            
            self._is_connected = True
            logger.info(f"Successfully connected to Redis at {host}:{port}")
            return True
            
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {str(e)}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Close the Redis connection."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self._is_connected = False
            logger.info("Disconnected from Redis")
    
    def is_connected(self) -> bool:
        """Check if the connector is currently connected."""
        if not self._is_connected or not self.client:
            return False
        
        try:
            self.client.ping()
            return True
        except Exception:
            self._is_connected = False
            return False
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a Redis command.
        
        Args:
            query: Redis command name (e.g., 'GET', 'SET', 'HGET', etc.)
            params: Dictionary containing:
                - key: Key for the operation
                - value: Value for SET operations
                - field: Field name for hash operations
                - ttl: Time to live in seconds for SET operations
                - operation: Specific operation details
                
        Returns:
            Result of the Redis command
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to Redis database")
        
        if not params:
            params = {}
        
        command = query.upper()
        key = params.get('key')
        
        try:
            if command == 'GET':
                if not key:
                    raise ValueError("key parameter required for GET")
                value = self.client.get(key)
                return [{'key': key, 'value': value}] if value is not None else []
                
            elif command == 'SET':
                if not key:
                    raise ValueError("key parameter required for SET")
                value = params.get('value')
                if value is None:
                    raise ValueError("value parameter required for SET")
                ttl = params.get('ttl')
                if ttl:
                    result = self.client.setex(key, ttl, value)
                else:
                    result = self.client.set(key, value)
                return [{'success': result}]
                
            elif command == 'DELETE' or command == 'DEL':
                if not key:
                    raise ValueError("key parameter required for DELETE")
                result = self.client.delete(key)
                return [{'deleted_count': result}]
                
            elif command == 'EXISTS':
                if not key:
                    raise ValueError("key parameter required for EXISTS")
                result = self.client.exists(key)
                return [{'exists': bool(result)}]
                
            elif command == 'KEYS':
                pattern = params.get('pattern', '*')
                keys = self.client.keys(pattern)
                return [{'keys': keys}]
                
            elif command == 'HGET':
                if not key:
                    raise ValueError("key parameter required for HGET")
                field = params.get('field')
                if not field:
                    raise ValueError("field parameter required for HGET")
                value = self.client.hget(key, field)
                return [{'key': key, 'field': field, 'value': value}] if value is not None else []
                
            elif command == 'HSET':
                if not key:
                    raise ValueError("key parameter required for HSET")
                field = params.get('field')
                value = params.get('value')
                if not field or value is None:
                    raise ValueError("field and value parameters required for HSET")
                result = self.client.hset(key, field, value)
                return [{'success': bool(result)}]
                
            elif command == 'HGETALL':
                if not key:
                    raise ValueError("key parameter required for HGETALL")
                result = self.client.hgetall(key)
                return [{'key': key, 'data': result}]
                
            elif command == 'LPUSH':
                if not key:
                    raise ValueError("key parameter required for LPUSH")
                values = params.get('values', [])
                if not values:
                    raise ValueError("values parameter required for LPUSH")
                result = self.client.lpush(key, *values)
                return [{'length': result}]
                
            elif command == 'RPUSH':
                if not key:
                    raise ValueError("key parameter required for RPUSH")
                values = params.get('values', [])
                if not values:
                    raise ValueError("values parameter required for RPUSH")
                result = self.client.rpush(key, *values)
                return [{'length': result}]
                
            elif command == 'LRANGE':
                if not key:
                    raise ValueError("key parameter required for LRANGE")
                start = params.get('start', 0)
                end = params.get('end', -1)
                result = self.client.lrange(key, start, end)
                return [{'key': key, 'values': result}]
                
            elif command == 'TTL':
                if not key:
                    raise ValueError("key parameter required for TTL")
                result = self.client.ttl(key)
                return [{'key': key, 'ttl': result}]
                
            else:
                # Generic command execution
                args = params.get('args', [])
                result = self.client.execute_command(command, *args)
                return [{'result': result}]
                
        except Exception as e:
            logger.error(f"Error executing Redis command: {str(e)}")
            raise
    
    def health_check(self) -> bool:
        """
        Perform a health check on the Redis connection.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            if not self.is_connected():
                return False
            
            # Ping the server
            result = self.client.ping()
            return result is True
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

