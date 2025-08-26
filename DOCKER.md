# Docker Setup

## Quick Start

```bash
# Development
docker-compose up -d

# Production with secrets
JWT_SECRET="your-32-char-secret" docker-compose up -d
```

## Configuration

Set these environment variables:

**Required for production:**
- `JWT_SECRET` - Strong secret key (32+ characters)
- `ADMIN_PASSWORD` - Change from default

**Optional:**
- `OPENAI_API_KEY` - For OpenAI code generation
- `GEMINI_API_KEY` - For Gemini code generation

## Production Considerations

1. **Use Docker secrets instead of environment variables:**
```yaml
secrets:
  jwt_secret:
    file: ./secrets/jwt_secret.txt
```

2. **Enable resource limits** (included in docker-compose.yml)

3. **Monitor containers:**
```bash
docker logs mcp-server
docker stats mcp-server
```

## Build Options

**Development:**
```bash
docker-compose up --build
```

**Production multi-stage build:**
```bash
docker build --target production -t mcp-server:prod .
```

## Troubleshooting

**Permissions:**
```bash
chmod -R 755 shared_host_folder logs
```

**Health check:**
```bash
curl http://localhost:8000/health
```