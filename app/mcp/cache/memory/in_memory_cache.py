
"""
In-memory cache implementation for the Model Context Protocol (MCP).

This module provides a thread-safe in-memory cache with LRU eviction.
"""

import asyncio
import time
from collections import OrderedDict
from typing import Any, Dict, Generic, Optional, TypeVar

# Type variable for cache values
T = TypeVar('T')


class CacheEntry(Generic[T]):
    """Represents a cached item with metadata."""
    
    def __init__(self, value: T, expiry: Optional[float] = None):
        """Initialize a cache entry.
        
        Args:
            value: The cached value
            expiry: Expiration timestamp (None for no expiration)
        """
        self.value = value
        self.expiry = expiry
        self.created_at = time.time()
        self.access_count = 0
        self.last_accessed = self.created_at
    
    def is_expired(self) -> bool:
        """Check if the entry has expired.
        
        Returns:
            bool: True if expired, False otherwise
        """
        if self.expiry is None:
            return False
        return time.time() > self.expiry
    
    def access(self) -> None:
        """Record an access to this entry."""
        self.access_count += 1
        self.last_accessed = time.time()


class Cache(Generic[T]):
    """Abstract base class for cache implementations."""
    
    async def get(self, key: str) -> Optional[T]:
        """Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Optional[T]: The cached value, or None if not found
        """
        raise NotImplementedError
    
    async def set(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> bool:
        """Set a value in the cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (None for no expiration)
            
        Returns:
            bool: True if successful
        """
        raise NotImplementedError
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if the key was found and deleted
        """
        raise NotImplementedError
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if the key exists and is not expired
        """
        raise NotImplementedError
    
    async def clear(self) -> bool:
        """Clear all values from the cache.
        
        Returns:
            bool: True if successful
        """
        raise NotImplementedError
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict[str, Any]: Cache statistics
        """
        raise NotImplementedError


class InMemoryCache(Cache[T]):
    """Thread-safe in-memory cache implementation with LRU eviction."""
    
    def __init__(self, max_size: int = 1000, default_ttl_seconds: Optional[int] = 300):
        """Initialize the in-memory cache.
        
        Args:
            max_size: Maximum number of items in the cache
            default_ttl_seconds: Default TTL for items (None for no expiration)
        """
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl_seconds = default_ttl_seconds
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._created_at = time.time()
    
    async def get(self, key: str) -> Optional[T]:
        """Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Optional[T]: The cached value, or None if not found
        """
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            
            # Move to end for LRU
            self._cache.move_to_end(key)
            entry.access()
            self._hits += 1
            
            return entry.value
    
    async def set(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> bool:
        """Set a value in the cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (None for default TTL)
            
        Returns:
            bool: True if successful
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        expiry = time.time() + ttl if ttl is not None else None
        
        async with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self._max_size and key not in self._cache:
                # Evict least recently used
                self._cache.popitem(last=False)
                self._evictions += 1
            
            # Add or update entry
            self._cache[key] = CacheEntry(value, expiry)
            # Move to end for LRU
            self._cache.move_to_end(key)
            
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if the key was found and deleted
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if the key exists and is not expired
        """
        async with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                return False
            
            return True
    
    async def clear(self) -> bool:
        """Clear all values from the cache.
        
        Returns:
            bool: True if successful
        """
        async with self._lock:
            self._cache.clear()
            return True
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict[str, Any]: Cache statistics
        """
        async with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "uptime_seconds": time.time() - self._created_at
            }
    
    async def _cleanup_expired(self) -> int:
        """Remove expired entries from the cache.
        
        Returns:
            int: Number of entries removed
        """
        removed = 0
        async with self._lock:
            keys_to_remove = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
                removed += 1
        
        return removed


class CacheManager(Generic[T]):
    """Manages multiple cache layers with different policies."""
    
    def __init__(self, l1_cache: Cache[T], l2_cache: Optional[Cache[T]] = None):
        """Initialize the cache manager.
        
        Args:
            l1_cache: Primary (fastest) cache
            l2_cache: Secondary cache (optional)
        """
        self._l1_cache = l1_cache
        self._l2_cache = l2_cache
        self._stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
            "writes": 0
        }
    
    async def get(self, key: str) -> Optional[T]:
        """Get a value from the cache hierarchy.
        
        Args:
            key: Cache key
            
        Returns:
            Optional[T]: The cached value, or None if not found
        """
        # Try L1 cache first
        value = await self._l1_cache.get(key)
        
        if value is not None:
            self._stats["l1_hits"] += 1
            return value
        
        # Try L2 cache if available
        if self._l2_cache:
            value = await self._l2_cache.get(key)
            
            if value is not None:
                # Populate L1 cache
                await self._l1_cache.set(key, value)
                self._stats["l2_hits"] += 1
                return value
        
        self._stats["misses"] += 1
        return None
    
    async def set(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> bool:
        """Set a value in all cache layers.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds
            
        Returns:
            bool: True if successful
        """
        self._stats["writes"] += 1
        
        # Set in L1 cache
        await self._l1_cache.set(key, value, ttl_seconds)
        
        # Set in L2 cache if available
        if self._l2_cache:
            await self._l2_cache.set(key, value, ttl_seconds)
        
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete a value from all cache layers.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if the key was found and deleted from any layer
        """
        result1 = await self._l1_cache.delete(key)
        
        if self._l2_cache:
            result2 = await self._l2_cache.delete(key)
            return result1 or result2
        
        return result1
    
    async def clear(self) -> bool:
        """Clear all cache layers.
        
        Returns:
            bool: True if successful
        """
        result1 = await self._l1_cache.clear()
        
        if self._l2_cache:
            result2 = await self._l2_cache.clear()
            return result1 or result2
        
        return result1
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all cache layers.
        
        Returns:
            Dict[str, Any]: Cache statistics
        """
        l1_stats = await self._l1_cache.get_stats()
        
        stats = {
            "l1_cache": l1_stats,
            "l1_hits": self._stats["l1_hits"],
            "l2_hits": self._stats["l2_hits"],
            "misses": self._stats["misses"],
            "writes": self._stats["writes"],
            "total_requests": self._stats["l1_hits"] + self._stats["l2_hits"] + self._stats["misses"],
        }
        
        if self._l2_cache:
            l2_stats = await self._l2_cache.get_stats()
            stats["l2_cache"] = l2_stats
        
        # Calculate hit rates
        total_requests = stats["total_requests"]
        if total_requests > 0:
            stats["overall_hit_rate"] = (self._stats["l1_hits"] + self._stats["l2_hits"]) / total_requests
            stats["l1_hit_rate"] = self._stats["l1_hits"] / total_requests
            stats["l2_hit_rate"] = self._stats["l2_hits"] / total_requests if self._l2_cache else 0
        else:
            stats["overall_hit_rate"] = 0
            stats["l1_hit_rate"] = 0
            stats["l2_hit_rate"] = 0
        
        return stats
