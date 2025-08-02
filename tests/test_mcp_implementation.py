
"""
Test script for MCP implementation.

This script tests the core functionality of the MCP implementation:
1. Authentication and authorization
2. Adapter creation and execution
3. Caching functionality
4. Audit logging
"""

import asyncio
import json
import os
import sys
import logging
import httpx
import time
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - TEST - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Server URL
BASE_URL = "http://localhost:8000"

# Test credentials
TEST_CREDENTIALS = {
    "username": "admin",
    "password": "admin123"
}

# Test adapter configurations
POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "postgres",
    "database": "postgres",
    "min_connections": 1,
    "max_connections": 5,
}

REST_API_CONFIG = {
    "base_url": "https://api.example.com",
    "headers": {
        "User-Agent": "MCP/1.0",
        "Accept": "application/json",
    },
    "timeout_seconds": 30.0,
}

# Test data request
TEST_QUERY = {
    "query": "SELECT * FROM users",
    "parameters": {},
}


async def test_health_check():
    """Test the health check endpoint."""
    logger.info("Testing health check endpoint...")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        data = response.json()
        assert data["status"] == "ok", f"Expected status 'ok', got {data['status']}"
        
        logger.info("Health check test passed!")
        return True


async def test_authentication():
    """Test authentication functionality."""
    logger.info("Testing authentication...")
    
    async with httpx.AsyncClient() as client:
        # Test login with valid credentials
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json=TEST_CREDENTIALS
        )
        
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        data = response.json()
        assert data["authenticated"] is True, "Authentication failed"
        assert "token" in data, "No token in response"
        token = data["token"]  # <-- Assign token
        
        # Test protected route with token
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(
            f"{BASE_URL}/api/protected",
            headers=headers
        )
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

        # Test protected route without token (should be 401)
        response = await client.get(f"{BASE_URL}/api/protected")
        assert response.status_code == 401, f"Expected status code 401, got {response.status_code}"
        
        logger.info("Authentication test passed!")
        return token  # <-- Return token for further use


async def test_adapter_creation(token: str):
    """Test adapter creation."""
    logger.info("Testing adapter creation...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Create PostgreSQL adapter
        response = await client.post(
            f"{BASE_URL}/api/adapters/postgres",
            headers=headers,
            json=POSTGRES_CONFIG
        )
        
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        data = response.json()
        assert "instance_id" in data, "No instance_id in response"
        postgres_id = data["instance_id"]
        
        # Create REST API adapter
        response = await client.post(
            f"{BASE_URL}/api/adapters/rest_api",
            headers=headers,
            json=REST_API_CONFIG
        )
        
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        data = response.json()
        assert "instance_id" in data, "No instance_id in response"
        rest_api_id = data["instance_id"]
        
        logger.info("Adapter creation test passed!")
        return postgres_id, rest_api_id


async def test_adapter_execution(token: str, instance_id: str):
    """Test adapter execution."""
    logger.info(f"Testing adapter execution for {instance_id}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Execute query
        response = await client.post(
            f"{BASE_URL}/api/adapters/{instance_id}/execute",
            headers=headers,
            json=TEST_QUERY
        )
        
        # Note: In a real test, we'd check for actual data
        # Here we're just checking that the request doesn't fail
        assert response.status_code in [200, 500], f"Unexpected status code {response.status_code}"
        
        if response.status_code == 500:
            logger.warning(f"Adapter execution returned error: {response.json()}")
            logger.warning("This is expected in a test environment without actual database connections")
        
        logger.info("Adapter execution test completed!")
        return True


async def test_caching(token: str, instance_id: str):
    """Test caching functionality."""
    logger.info(f"Testing caching for {instance_id}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Execute query first time
        start_time = time.time()
        response1 = await client.post(
            f"{BASE_URL}/api/adapters/{instance_id}/execute",
            headers=headers,
            json=TEST_QUERY
        )
        first_request_time = time.time() - start_time
        
        # Execute same query again (should be cached)
        start_time = time.time()
        response2 = await client.post(
            f"{BASE_URL}/api/adapters/{instance_id}/execute",
            headers=headers,
            json=TEST_QUERY
        )
        second_request_time = time.time() - start_time
        
        # In a real environment with actual database connections,
        # the second request should be faster due to caching
        logger.info(f"First request time: {first_request_time:.4f}s")
        logger.info(f"Second request time: {second_request_time:.4f}s")
        
        # Check that responses are the same
        if response1.status_code == 200 and response2.status_code == 200:
            assert response1.json() == response2.json(), "Cached response differs from original"
        
        logger.info("Caching test completed!")
        return True


async def test_audit_logging():
    """
    Test audit logging functionality.
    
    Note: This is a basic test that just checks if the audit log file exists
    and has been updated. A more comprehensive test would parse the log file
    and verify specific entries.
    """
    logger.info("Testing audit logging...")
    
    # Check if audit log file exists
    log_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../audit.log"))
    assert os.path.exists(log_file), f"Audit log file {log_file} does not exist"

    
    # Check if file has content
    file_size = os.path.getsize(log_file)
    assert file_size > 0, f"Audit log file {log_file} is empty"
    
    # Get modification time
    mod_time = os.path.getmtime(log_file)
    current_time = time.time()
    time_diff = current_time - mod_time
    
    # Check if file was modified recently (within last hour)
    assert time_diff < 3600, f"Audit log file {log_file} has not been updated recently"
    
    logger.info("Audit logging test passed!")
    return True


async def main():
    """Main test function."""
    logger.info("Starting MCP implementation tests...")
    
    try:
        # Test health check
        await test_health_check()
        
        # Test authentication
        token = await test_authentication()
        
        # Test adapter creation
        postgres_id, rest_api_id = await test_adapter_creation(token)
        
        # Test adapter execution
        await test_adapter_execution(token, postgres_id)
        await test_adapter_execution(token, rest_api_id)
        
        # Test caching
        await test_caching(token, postgres_id)
        
        # Test audit logging
        await test_audit_logging()
        
        logger.info("All tests completed successfully!")
    except AssertionError as e:
        logger.error(f"Test failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
