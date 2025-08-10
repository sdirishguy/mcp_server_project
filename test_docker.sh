#!/bin/bash

# Test script for Docker container functionality

echo "🧪 Testing MCP Server Docker Container"
echo "======================================"

# Test 1: Health check
echo "1. Testing health endpoint..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi

# Test 2: Server info
echo "2. Testing server info endpoint..."
if curl -f http://localhost:8000/whoami > /dev/null 2>&1; then
    echo "✅ Server info endpoint working"
else
    echo "❌ Server info endpoint failed"
    exit 1
fi

# Test 3: Authentication
echo "3. Testing authentication..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "admin123"}')

if echo "$LOGIN_RESPONSE" | grep -q '"authenticated":true'; then
    echo "✅ Authentication successful"
    TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
    echo "   Token: $TOKEN"
else
    echo "❌ Authentication failed"
    echo "   Response: $LOGIN_RESPONSE"
    exit 1
fi

# Test 4: Adapter creation
echo "4. Testing adapter creation..."
ADAPTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/adapters/rest_api \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name": "test-adapter", "base_url": "https://httpbin.org", "headers": {}, "timeout": 10}')

if echo "$ADAPTER_RESPONSE" | grep -q '"message":"Adapter created"'; then
    echo "✅ Adapter creation successful"
    INSTANCE_ID=$(echo "$ADAPTER_RESPONSE" | grep -o '"instance_id":"[^"]*"' | cut -d'"' -f4)
    echo "   Instance ID: $INSTANCE_ID"
else
    echo "❌ Adapter creation failed"
    echo "   Response: $ADAPTER_RESPONSE"
    exit 1
fi

# Test 5: Adapter execution
echo "5. Testing adapter execution..."
EXECUTE_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/adapters/$INSTANCE_ID/execute" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"method": "get", "path": "/users", "params": {"test": "value"}}')

if echo "$EXECUTE_RESPONSE" | grep -q '"status_code":200'; then
    echo "✅ Adapter execution successful"
else
    echo "❌ Adapter execution failed"
    echo "   Response: $EXECUTE_RESPONSE"
    exit 1
fi

# Test 6: Check logs directory
echo "6. Testing log file creation..."
if [ -f "./logs/audit.log" ]; then
    echo "✅ Audit log file created"
    echo "   Log entries: $(wc -l < ./logs/audit.log)"
else
    echo "❌ Audit log file not found"
    exit 1
fi

# Test 7: Check container status
echo "7. Checking container status..."
if docker ps | grep -q "mcp-server"; then
    echo "✅ Container is running"
    CONTAINER_ID=$(docker ps | grep "mcp-server" | awk '{print $1}')
    echo "   Container ID: $CONTAINER_ID"
else
    echo "❌ Container is not running"
    exit 1
fi

echo ""
echo "🎉 All tests passed! The MCP Server is fully operational in Docker."
echo ""
echo "📋 Summary:"
echo "   - Health endpoint: ✅"
echo "   - Authentication: ✅"
echo "   - Adapter creation: ✅"
echo "   - Adapter execution: ✅"
echo "   - Logging: ✅"
echo "   - Container status: ✅"
echo ""
echo "🌐 Server is accessible at: http://localhost:8000"
echo "📚 API documentation: See DOCKER.md for usage instructions"
