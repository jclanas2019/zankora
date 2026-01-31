# Deployment Guide

This guide covers best practices for deploying Agent Gateway in production environments.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Configuration](#environment-configuration)
3. [Database Setup](#database-setup)
4. [Security Hardening](#security-hardening)
5. [Container Deployment](#container-deployment)
6. [Kubernetes Deployment](#kubernetes-deployment)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [Backup & Recovery](#backup--recovery)
9. [Performance Tuning](#performance-tuning)
10. [Troubleshooting](#troubleshooting)

## Pre-Deployment Checklist

Before deploying to production:

- [ ] Security audit completed
- [ ] Load testing performed
- [ ] Backup strategy defined
- [ ] Monitoring configured
- [ ] API keys rotated from dev defaults
- [ ] Database migrations tested
- [ ] SSL/TLS certificates obtained
- [ ] Disaster recovery plan documented
- [ ] Team trained on operations

## Environment Configuration

### Production Environment Variables

```env
# Security (CRITICAL - Never use dev keys!)
AGW_REQUIRE_CLIENT_AUTH=true
AGW_CLIENT_API_KEYS=["$(openssl rand -base64 32)"]
AGW_REQUIRE_APPROVALS_FOR_WRITE_TOOLS=true

# Server
AGW_HOST=0.0.0.0
AGW_PORT=8787
AGW_INSTANCE_ID=prod-gateway-01

# Database (PostgreSQL recommended)
AGW_DATABASE_URL=postgresql+asyncpg://user:password@db-host:5432/gateway_prod
AGW_DB_POOL_SIZE=20
AGW_DB_MAX_OVERFLOW=10

# Rate Limiting
AGW_RATE_LIMIT_RPS=100
AGW_RATE_LIMIT_BURST=200

# Logging
AGW_LOG_LEVEL=INFO
AGW_LOG_FORMAT=json
AGW_LOG_FILE_ENABLED=true
AGW_LOG_FILE_PATH=/var/log/agent-gateway/gateway.log

# Circuit Breaker
AGW_CIRCUIT_BREAKER_ENABLED=true
AGW_CIRCUIT_BREAKER_THRESHOLD=10
AGW_CIRCUIT_BREAKER_TIMEOUT=120

# LLM Provider
AGW_LLM_PROVIDER=anthropic
AGW_ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

### Secrets Management

**Never commit secrets to version control!**

Use a secrets manager:

```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id agent-gateway/prod/api-keys \
  --query SecretString --output text

# HashiCorp Vault
vault kv get secret/agent-gateway/prod/api-keys

# Kubernetes Secrets
kubectl create secret generic gateway-secrets \
  --from-literal=api-key=$(openssl rand -base64 32) \
  --from-literal=db-password=<password>
```

## Database Setup

### PostgreSQL (Recommended for Production)

```bash
# Install PostgreSQL 16
sudo apt-get install postgresql-16

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE gateway_prod;
CREATE USER gateway WITH ENCRYPTED PASSWORD 'strong-password';
GRANT ALL PRIVILEGES ON DATABASE gateway_prod TO gateway;
\c gateway_prod
GRANT ALL ON SCHEMA public TO gateway;
EOF

# Run migrations
export AGW_DATABASE_URL="postgresql+asyncpg://gateway:password@localhost/gateway_prod"
alembic upgrade head
```

### Database Backup

```bash
# Automated daily backup
cat > /etc/cron.daily/gateway-backup <<'EOF'
#!/bin/bash
BACKUP_DIR=/var/backups/agent-gateway
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump gateway_prod | gzip > $BACKUP_DIR/gateway_$DATE.sql.gz
find $BACKUP_DIR -mtime +30 -delete  # Keep 30 days
EOF
chmod +x /etc/cron.daily/gateway-backup
```

## Security Hardening

### 1. Network Security

```nginx
# Nginx reverse proxy with SSL
server {
    listen 443 ssl http2;
    server_name gateway.example.com;
    
    ssl_certificate /etc/letsencrypt/live/gateway.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gateway.example.com/privkey.pem;
    
    # Strong SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # WebSocket proxy
    location /ws {
        proxy_pass http://localhost:8787/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
    
    # Metrics (restrict to monitoring network)
    location /metrics {
        allow 10.0.0.0/8;  # Internal network
        deny all;
        proxy_pass http://localhost:8787/metrics;
    }
    
    # Health check
    location /healthz {
        proxy_pass http://localhost:8787/healthz;
    }
}
```

### 2. Firewall Rules

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# Restrict gateway port to localhost only
sudo ufw deny 8787
```

### 3. Application Security

```env
# Enable all security features
AGW_REQUIRE_CLIENT_AUTH=true
AGW_REQUIRE_APPROVALS_FOR_WRITE_TOOLS=true
AGW_RATE_LIMIT_RPS=100
AGW_CIRCUIT_BREAKER_ENABLED=true
```

## Container Deployment

### Docker

```bash
# Build production image
docker build -t agent-gateway:1.0.0 .

# Run with secrets
docker run -d \
  --name agent-gateway \
  --restart unless-stopped \
  -p 8787:8787 \
  -v /var/log/agent-gateway:/app/logs \
  -v /var/lib/agent-gateway:/app/data \
  --env-file /etc/agent-gateway/.env.prod \
  --memory 2g \
  --cpus 2 \
  agent-gateway:1.0.0
```

### Docker Compose (Production)

```yaml
version: '3.8'

services:
  gateway:
    image: agent-gateway:1.0.0
    restart: always
    ports:
      - "127.0.0.1:8787:8787"
    volumes:
      - /var/log/agent-gateway:/app/logs
      - /var/lib/agent-gateway/data:/app/data
      - /var/lib/agent-gateway/plugins:/app/plugins
    env_file:
      - /etc/agent-gateway/.env.prod
    depends_on:
      - postgres
      - redis
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8787/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: gateway_prod
      POSTGRES_USER: gateway
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:

secrets:
  db_password:
    file: /run/secrets/postgres_password
```

## Kubernetes Deployment

### Deployment Manifest

```yaml
# gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-gateway
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agent-gateway
  template:
    metadata:
      labels:
        app: agent-gateway
    spec:
      containers:
      - name: gateway
        image: agent-gateway:1.0.0
        ports:
        - containerPort: 8787
          name: http
        env:
        - name: AGW_HOST
          value: "0.0.0.0"
        - name: AGW_DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: gateway-secrets
              key: database-url
        - name: AGW_CLIENT_API_KEYS
          valueFrom:
            secretKeyRef:
              name: gateway-secrets
              key: api-keys
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8787
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8787
          initialDelaySeconds: 10
          periodSeconds: 10
        volumeMounts:
        - name: data
          mountPath: /app/data
        - name: plugins
          mountPath: /app/plugins
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: gateway-data-pvc
      - name: plugins
        configMap:
          name: gateway-plugins

---
apiVersion: v1
kind: Service
metadata:
  name: agent-gateway
  namespace: production
spec:
  selector:
    app: agent-gateway
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8787
  type: ClusterIP
```

## Monitoring & Alerting

### Prometheus Alerts

```yaml
# alerts.yml
groups:
- name: agent-gateway
  interval: 30s
  rules:
  - alert: GatewayDown
    expr: up{job="agent-gateway"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Agent Gateway is down"
      
  - alert: HighErrorRate
    expr: rate(agw_agent_runs_total{status="failed"}[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
      
  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(agw_request_duration_seconds_bucket[5m])) > 5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High latency detected (p95 > 5s)"
```

### Grafana Dashboard

Import the pre-built dashboard from `monitoring/grafana-dashboard.json` or create custom panels for:

- Request rate and latency
- Error rates by type
- Active connections
- Circuit breaker states
- Database connection pool usage
- Memory and CPU usage

## Backup & Recovery

### Backup Strategy

1. **Database**: Daily PostgreSQL dumps
2. **Configuration**: Version controlled `.env` files
3. **Data Directory**: Daily rsync to backup server
4. **Plugins**: Version controlled in Git

### Recovery Procedure

```bash
# 1. Restore database
gunzip < /var/backups/gateway_20260130.sql.gz | psql gateway_prod

# 2. Restore data directory
rsync -av /var/backups/agent-gateway/data/ /var/lib/agent-gateway/data/

# 3. Restart service
docker-compose restart gateway
# or
kubectl rollout restart deployment/agent-gateway

# 4. Verify health
curl http://localhost:8787/healthz
```

## Performance Tuning

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX idx_messages_chat_id ON messages(chat_id);
CREATE INDEX idx_events_run_id ON events(run_id);
CREATE INDEX idx_runs_status ON agent_runs(status);

-- Vacuum and analyze
VACUUM ANALYZE;
```

### Application Tuning

```env
# Increase pool size for high traffic
AGW_DB_POOL_SIZE=50
AGW_DB_MAX_OVERFLOW=20

# Adjust rate limits
AGW_RATE_LIMIT_RPS=500
AGW_RATE_LIMIT_BURST=1000

# Increase timeouts
AGW_RUN_TIMEOUT_S=600
AGW_WS_PING_TIMEOUT=30
```

## Troubleshooting

### Common Issues

**Issue: High memory usage**
```bash
# Check memory usage
docker stats agent-gateway

# Reduce pool size
AGW_DB_POOL_SIZE=10
AGW_EVENT_BUS_QUEUE_SIZE=500
```

**Issue: Database connection errors**
```bash
# Check connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'gateway_prod';

# Increase pool
AGW_DB_POOL_SIZE=30
```

**Issue: WebSocket disconnections**
```bash
# Increase timeouts
AGW_WS_PING_INTERVAL=60
AGW_WS_PING_TIMEOUT=20
```

### Log Analysis

```bash
# Tail JSON logs
tail -f /var/log/agent-gateway/gateway.log | jq .

# Find errors
grep '"level":"error"' /var/log/agent-gateway/gateway.log | jq .

# Count requests by status
jq -r .status /var/log/agent-gateway/gateway.log | sort | uniq -c
```

## Maintenance

### Regular Tasks

- **Daily**: Check error logs and metrics
- **Weekly**: Review security alerts, backup verification
- **Monthly**: Update dependencies, rotate API keys
- **Quarterly**: Security audit, load testing

### Updates

```bash
# Zero-downtime rolling update (Kubernetes)
kubectl set image deployment/agent-gateway \
  gateway=agent-gateway:1.1.0

kubectl rollout status deployment/agent-gateway

# Rollback if needed
kubectl rollout undo deployment/agent-gateway
```

## Support

For production support:
- Emergency: Create priority ticket
- Documentation: See `docs/` directory
- Community: GitHub Discussions
