# Deployment Guide

## Overview

This guide covers deploying the cloud management platform from development to production, including infrastructure setup, configuration, scaling, and operational procedures.

## Deployment Environments

### 1. Development
- Local Docker Compose setup
- Minimal resources
- Mock Proxmox API for testing
- Hot-reload enabled
- Debug logging

### 2. Staging
- Kubernetes cluster (3 nodes minimum)
- Production-like configuration
- Connects to test Proxmox cluster
- Blue-green deployment
- Integration testing

### 3. Production
- Kubernetes cluster (multi-region if large scale)
- High availability for all components
- Multiple Proxmox clusters
- Automated backups
- Monitoring and alerting
- Disaster recovery procedures

## Infrastructure Requirements

### Minimum Production Setup (Small Scale)

**Control Plane (Application Layer):**
- 3x Application Servers (8 vCPU, 16GB RAM each)
- 1x Database Server (8 vCPU, 32GB RAM, 500GB SSD)
- 1x Redis Server (4 vCPU, 8GB RAM)
- 1x RabbitMQ Server (4 vCPU, 8GB RAM)
- 1x Load Balancer (4 vCPU, 8GB RAM)

**For Large Scale (500+ users):**
- 6-9x Application Servers (16 vCPU, 32GB RAM each)
- PostgreSQL Cluster (3 nodes: 1 primary + 2 replicas, 16 vCPU, 64GB RAM each)
- Redis Cluster (3 nodes, 8 vCPU, 16GB RAM each)
- RabbitMQ Cluster (3 nodes, 8 vCPU, 16GB RAM each)
- Load Balancer pair (HA, 8 vCPU, 16GB RAM each)
- TimescaleDB dedicated instance (16 vCPU, 64GB RAM)
- Monitoring stack (Prometheus, Grafana, Loki)

**Network Requirements:**
- High-bandwidth connection to Proxmox clusters (1Gbps+)
- Low latency to database (<5ms)
- External internet access for API
- Private network for internal services

### Proxmox Infrastructure

**Minimum:**
- 1 Proxmox cluster (3 nodes)
- Shared storage (Ceph, NFS, or iSCSI)

**Recommended for Large Scale:**
- Multiple Proxmox clusters (3-5 nodes each)
- Distributed across datacenters
- Dedicated storage per cluster
- Management network separation

## Deployment Options

### Option 1: Docker Compose (Development/Small Deployments)

**Best for:**
- Development environments
- Small deployments (<50 users)
- Single-server setups
- Quick proof-of-concept

**Limitations:**
- No auto-scaling
- Limited high availability
- Manual updates
- Single point of failure

### Option 2: Kubernetes (Recommended for Production)

**Best for:**
- Production deployments
- Large scale (500+ users)
- Multi-region deployments
- Auto-scaling required
- High availability needed

**Benefits:**
- Auto-scaling
- Self-healing
- Rolling updates
- Service discovery
- Load balancing
- Easy monitoring integration

## Kubernetes Deployment

### Cluster Setup

#### Prerequisites

1. **Kubernetes Cluster**: v1.28+
2. **kubectl**: Configured to access cluster
3. **Helm**: v3.12+ installed
4. **Container Registry**: Docker Hub, Harbor, or AWS ECR
5. **Storage Class**: For persistent volumes
6. **Ingress Controller**: NGINX Ingress or Traefik

#### Cluster Architecture

```
┌─────────────────────────────────────────────────────┐
│              Ingress Controller                      │
│         (NGINX / Traefik / Kong)                    │
└─────────────────┬───────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┬──────────────┐
    │             │             │              │
    ▼             ▼             ▼              ▼
┌────────┐   ┌────────┐   ┌─────────┐   ┌──────────┐
│  API   │   │  API   │   │   API   │   │ Frontend │
│ Pod 1  │   │ Pod 2  │   │  Pod 3  │   │   Pods   │
└────────┘   └────────┘   └─────────┘   └──────────┘
    │             │             │              │
    └─────────────┼─────────────┴──────────────┘
                  │
    ┌─────────────┼─────────────┬──────────────┐
    │             │             │              │
    ▼             ▼             ▼              ▼
┌─────────┐  ┌────────┐   ┌─────────┐  ┌──────────┐
│ Postgres│  │ Redis  │   │RabbitMQ │  │  Celery  │
│StatefulS│  │Cluster │   │ Cluster │  │ Workers  │
│   et    │  │        │   │         │  │          │
└─────────┘  └────────┘   └─────────┘  └──────────┘
```

### Namespace Structure

```bash
# Create namespaces
kubectl create namespace cloudplatform-prod
kubectl create namespace cloudplatform-staging
kubectl create namespace monitoring
```

### Secrets Management

#### Create Secrets

```bash
# Database credentials
kubectl create secret generic postgres-credentials \
  --from-literal=username=cloudplatform \
  --from-literal=password=STRONG_PASSWORD \
  -n cloudplatform-prod

# Redis password
kubectl create secret generic redis-credentials \
  --from-literal=password=REDIS_PASSWORD \
  -n cloudplatform-prod

# JWT secret
kubectl create secret generic jwt-secret \
  --from-literal=secret-key=RANDOM_SECRET_KEY \
  -n cloudplatform-prod

# Proxmox credentials
kubectl create secret generic proxmox-credentials \
  --from-literal=api-token=PROXMOX_TOKEN \
  -n cloudplatform-prod
```

**Better approach:** Use **HashiCorp Vault** or **Sealed Secrets** for production.

### ConfigMaps

```yaml
# config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
  namespace: cloudplatform-prod
data:
  LOG_LEVEL: "info"
  ENVIRONMENT: "production"
  API_VERSION: "v1"
  DATABASE_POOL_SIZE: "20"
  REDIS_DB: "0"
  CORS_ORIGINS: "https://portal.example.com"
```

### Database Deployment

#### PostgreSQL StatefulSet

```yaml
# postgres-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: cloudplatform-prod
spec:
  serviceName: postgres
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: timescale/timescaledb:2.13-pg16
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: cloudplatform
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: password
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            cpu: 2000m
            memory: 8Gi
          limits:
            cpu: 4000m
            memory: 16Gi
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 500Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: cloudplatform-prod
spec:
  clusterIP: None
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
```

**Alternative:** Use managed PostgreSQL (AWS RDS, GCP Cloud SQL, Azure Database)

#### Redis Deployment

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: cloudplatform-prod
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        args:
        - --requirepass
        - $(REDIS_PASSWORD)
        - --maxmemory
        - 4gb
        - --maxmemory-policy
        - allkeys-lru
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: redis-credentials
              key: password
        resources:
          requests:
            cpu: 500m
            memory: 2Gi
          limits:
            cpu: 1000m
            memory: 4Gi
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: cloudplatform-prod
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

**For production:** Use Redis Cluster or managed Redis (AWS ElastiCache, Azure Cache for Redis)

### API Service Deployment

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: cloudplatform-prod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: cloudplatform/api:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: postgresql://$(DB_USER):$(DB_PASSWORD)@postgres:5432/cloudplatform
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: password
        - name: REDIS_URL
          value: redis://:$(REDIS_PASSWORD)@redis:6379/0
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: redis-credentials
              key: password
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: secret-key
        envFrom:
        - configMapRef:
            name: api-config
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            cpu: 1000m
            memory: 2Gi
          limits:
            cpu: 2000m
            memory: 4Gi
---
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: cloudplatform-prod
spec:
  selector:
    app: api
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

### Celery Workers Deployment

```yaml
# celery-worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
  namespace: cloudplatform-prod
spec:
  replicas: 5
  selector:
    matchLabels:
      app: celery-worker
  template:
    metadata:
      labels:
        app: celery-worker
    spec:
      containers:
      - name: celery-worker
        image: cloudplatform/api:v1.0.0
        command: ["celery"]
        args:
        - "-A"
        - "app.celery_app"
        - "worker"
        - "--loglevel=info"
        - "--concurrency=4"
        env:
        # Same env vars as API
        - name: DATABASE_URL
          value: postgresql://$(DB_USER):$(DB_PASSWORD)@postgres:5432/cloudplatform
        # ... (same as API)
        resources:
          requests:
            cpu: 1000m
            memory: 2Gi
          limits:
            cpu: 2000m
            memory: 4Gi
```

### Celery Beat Deployment

```yaml
# celery-beat-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-beat
  namespace: cloudplatform-prod
spec:
  replicas: 1  # Only 1 beat scheduler needed
  selector:
    matchLabels:
      app: celery-beat
  template:
    metadata:
      labels:
        app: celery-beat
    spec:
      containers:
      - name: celery-beat
        image: cloudplatform/api:v1.0.0
        command: ["celery"]
        args:
        - "-A"
        - "app.celery_app"
        - "beat"
        - "--loglevel=info"
        env:
        # Same env vars as API
        resources:
          requests:
            cpu: 200m
            memory: 512Mi
```

### Ingress Configuration

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cloudplatform-ingress
  namespace: cloudplatform-prod
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.cloudplatform.example.com
    - portal.cloudplatform.example.com
    secretName: cloudplatform-tls
  rules:
  - host: api.cloudplatform.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 8000
  - host: portal.cloudplatform.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
```

### HorizontalPodAutoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
  namespace: cloudplatform-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Helm Chart Deployment (Recommended)

### Create Helm Chart Structure

```
cloudplatform-chart/
├── Chart.yaml
├── values.yaml
├── values-prod.yaml
├── values-staging.yaml
└── templates/
    ├── api-deployment.yaml
    ├── api-service.yaml
    ├── postgres-statefulset.yaml
    ├── redis-deployment.yaml
    ├── celery-worker-deployment.yaml
    ├── ingress.yaml
    ├── hpa.yaml
    ├── configmap.yaml
    └── secrets.yaml
```

### Install with Helm

```bash
# Add custom Helm repo (if published)
helm repo add cloudplatform https://charts.cloudplatform.example.com

# Install to production
helm install cloudplatform cloudplatform/cloudplatform \
  --namespace cloudplatform-prod \
  --values values-prod.yaml \
  --create-namespace

# Upgrade
helm upgrade cloudplatform cloudplatform/cloudplatform \
  --namespace cloudplatform-prod \
  --values values-prod.yaml

# Rollback if needed
helm rollback cloudplatform -n cloudplatform-prod
```

## Database Migrations

### Running Migrations

```bash
# Create migration job
kubectl create job migrate-$(date +%s) \
  --from=cronjob/database-migration \
  -n cloudplatform-prod

# Or run manually
kubectl run migrate --rm -it \
  --image=cloudplatform/api:v1.0.0 \
  --restart=Never \
  --command -- alembic upgrade head
```

### Automated Migration Job

```yaml
# migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: database-migration
  namespace: cloudplatform-prod
spec:
  template:
    spec:
      containers:
      - name: migrate
        image: cloudplatform/api:v1.0.0
        command: ["alembic", "upgrade", "head"]
        env:
        - name: DATABASE_URL
          value: postgresql://...
      restartPolicy: OnFailure
```

## Monitoring Setup

### Prometheus + Grafana

```bash
# Install Prometheus Operator
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace

# Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Default credentials: admin / prom-operator
```

### ServiceMonitor for API

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-metrics
  namespace: cloudplatform-prod
spec:
  selector:
    matchLabels:
      app: api
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
```

### Custom Dashboards

Import pre-built dashboards for:
- FastAPI metrics
- PostgreSQL metrics
- Redis metrics
- RabbitMQ metrics
- Celery metrics

## Logging Setup

### Loki Stack

```bash
# Install Loki
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set grafana.enabled=false \
  --set prometheus.enabled=false
```

### Log Aggregation

All container logs automatically forwarded to Loki via Promtail.

## Backup & Disaster Recovery

### Database Backups

#### Automated Backup CronJob

```yaml
# backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: cloudplatform-prod
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:16
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -h postgres -U cloudplatform cloudplatform | \
              gzip > /backup/cloudplatform-$(date +%Y%m%d).sql.gz && \
              aws s3 cp /backup/cloudplatform-$(date +%Y%m%d).sql.gz s3://backups/
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-credentials
                  key: password
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          restartPolicy: OnFailure
          volumes:
          - name: backup-storage
            emptyDir: {}
```

### Backup Strategy

- **Frequency**: Daily full backup + WAL archiving (continuous)
- **Retention**: 30 days of daily backups
- **Storage**: S3-compatible object storage (MinIO, AWS S3, Backblaze B2)
- **Encryption**: Encrypt backups at rest
- **Testing**: Monthly restore test

### Disaster Recovery

#### RTO (Recovery Time Objective): 4 hours
#### RPO (Recovery Point Objective): 1 hour

**Recovery Procedure:**

1. **Database Failure:**
   ```bash
   # Promote read replica to primary
   kubectl exec -it postgres-1 -- pg_ctl promote

   # Update application config
   kubectl set env deployment/api DATABASE_URL=postgresql://postgres-1:5432/cloudplatform
   ```

2. **Complete Cluster Failure:**
   ```bash
   # Restore from backup
   aws s3 cp s3://backups/cloudplatform-20260131.sql.gz .
   gunzip cloudplatform-20260131.sql.gz
   psql -h new-postgres -U cloudplatform cloudplatform < cloudplatform-20260131.sql

   # Restore from WAL archives
   # (if using continuous archiving)
   ```

3. **Application Failure:**
   ```bash
   # Rollback to previous version
   helm rollback cloudplatform -n cloudplatform-prod
   ```

## SSL/TLS Configuration

### Cert-Manager Setup

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

Certificates will be automatically provisioned and renewed.

## Zero-Downtime Deployment

### Rolling Update Strategy

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # Never have fewer than desired replicas
```

### Blue-Green Deployment (Advanced)

1. Deploy new version (green) alongside old version (blue)
2. Test green deployment
3. Switch traffic to green
4. Monitor for issues
5. Decommission blue if successful

```bash
# Deploy green
helm install cloudplatform-green ./chart --values values-prod.yaml

# Switch traffic (update Ingress)
kubectl patch ingress cloudplatform-ingress \
  -p '{"spec":{"rules":[{"host":"api.example.com","http":{"paths":[{"backend":{"service":{"name":"api-green"}}}]}}]}}'

# Decommission blue
helm uninstall cloudplatform-blue
```

## Performance Tuning

### Database Optimization

```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM virtual_machines WHERE organization_id = 'uuid';

-- Create indexes for common queries
CREATE INDEX CONCURRENTLY idx_vms_org_status
ON virtual_machines(organization_id, status)
WHERE deleted_at IS NULL;

-- Update statistics
ANALYZE virtual_machines;
```

### Redis Optimization

```
# redis.conf
maxmemory-policy allkeys-lru
maxmemory 4gb
tcp-backlog 511
timeout 300
```

### API Performance

- Enable response compression (gzip)
- Implement caching headers
- Use connection pooling
- Optimize database queries
- Add database read replicas

## Scaling Guidelines

### Vertical Scaling

Increase resources for individual components:

```bash
# Scale API pods
kubectl set resources deployment api \
  --requests=cpu=2000m,memory=4Gi \
  --limits=cpu=4000m,memory=8Gi \
  -n cloudplatform-prod
```

### Horizontal Scaling

Add more replicas:

```bash
# Manual scaling
kubectl scale deployment api --replicas=6 -n cloudplatform-prod

# Or use HPA (automatic)
```

### Database Scaling

- Add read replicas for read-heavy workloads
- Partition large tables (audit_logs, usage_records)
- Use connection pooling (PgBouncer)
- Consider sharding for extreme scale

## Security Hardening

### Network Policies

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
  namespace: cloudplatform-prod
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
```

### Pod Security Standards

```yaml
# pod-security.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: cloudplatform-prod
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

### RBAC

Implement least-privilege access for service accounts.

## Operational Procedures

### Health Checks

```bash
# Check API health
curl https://api.cloudplatform.example.com/health

# Check database connectivity
kubectl exec -it postgres-0 -n cloudplatform-prod -- psql -U cloudplatform -c "SELECT 1"

# Check Redis
kubectl exec -it redis-0 -n cloudplatform-prod -- redis-cli ping
```

### Log Access

```bash
# View API logs
kubectl logs -f deployment/api -n cloudplatform-prod

# View logs for specific pod
kubectl logs -f pod/api-abc123 -n cloudplatform-prod

# View logs from all replicas
kubectl logs -f -l app=api -n cloudplatform-prod
```

### Emergency Procedures

#### High CPU Usage

```bash
# Check pod CPU usage
kubectl top pods -n cloudplatform-prod

# Scale up immediately
kubectl scale deployment api --replicas=10 -n cloudplatform-prod

# Investigate
kubectl logs deployment/api --tail=100 -n cloudplatform-prod
```

#### Database Connection Exhaustion

```bash
# Check connections
kubectl exec -it postgres-0 -n cloudplatform-prod -- \
  psql -U cloudplatform -c "SELECT count(*) FROM pg_stat_activity"

# Kill idle connections
kubectl exec -it postgres-0 -n cloudplatform-prod -- \
  psql -U cloudplatform -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < NOW() - INTERVAL '5 minutes'"

# Increase max_connections (requires restart)
```

## Maintenance Windows

### Scheduled Maintenance

1. **Notify users** 48 hours in advance
2. **Enable maintenance mode** (return 503 with Retry-After header)
3. **Perform updates** (database migrations, application updates)
4. **Run smoke tests**
5. **Disable maintenance mode**
6. **Monitor** for 1 hour post-maintenance

### Maintenance Mode

```bash
# Enable maintenance mode
kubectl scale deployment api --replicas=0 -n cloudplatform-prod
kubectl apply -f maintenance-page.yaml
```

## Troubleshooting Guide

### Common Issues

**Issue:** API pods crash-looping
```bash
# Check logs
kubectl logs api-abc123 -n cloudplatform-prod --previous

# Check events
kubectl describe pod api-abc123 -n cloudplatform-prod

# Common causes:
# - Database connection failure
# - Missing environment variables
# - Out of memory
```

**Issue:** Slow API responses
```bash
# Check database performance
kubectl exec -it postgres-0 -n cloudplatform-prod -- \
  psql -U cloudplatform -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10"

# Check Redis latency
kubectl exec -it redis-0 -n cloudplatform-prod -- redis-cli --latency

# Check API metrics in Grafana
```

**Issue:** VM provisioning failures
```bash
# Check Celery worker logs
kubectl logs -f deployment/celery-worker -n cloudplatform-prod

# Check task status
kubectl exec -it api-abc123 -n cloudplatform-prod -- \
  python -m app.tasks.inspect

# Common causes:
# - Proxmox API unreachable
# - Resource quota exceeded
# - Storage full
```

## Cost Optimization

1. **Right-size pods** based on actual resource usage
2. **Use HPA** to scale down during low traffic
3. **Enable database connection pooling**
4. **Use read replicas** for read-heavy queries
5. **Implement caching** aggressively
6. **Use spot/preemptible instances** for worker nodes
7. **Monitor unused resources** and clean up

## Next Steps

1. Review all deployment files
2. Customize for your environment
3. Set up CI/CD pipeline
4. Deploy to staging first
5. Run load tests
6. Deploy to production
7. Configure monitoring and alerting
8. Document runbooks for your team

## Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Prometheus Documentation](https://prometheus.io/docs/)
