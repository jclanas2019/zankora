# Security hardening

## Default posture
- **deny-by-default**: inbound blocked unless allowlisted.
- tools are **deny-by-default** (must be explicitly enabled in `policy.tool_allow`).
- write tools can require **human approvals** (default ON).

## Recomendaciones para producción
1. **TLS + Auth**: termina TLS en reverse proxy; usa auth fuerte (OIDC) para el control-plane WS.
2. **Network**: no expongas 0.0.0.0 sin firewall; segmenta por VPC/subnet.
3. **Secrets**: usa secret manager; rota claves; nunca en repositorio.
4. **RBAC**: separa API keys por rol (viewer/operator/admin).
5. **Audit logs**: retención, shipping (ELK/Datadog), y correlación por `run_id`.
6. **Plugin trust**: firma plugins o allowlist por hash; ejecuta en sandbox si es posible.
7. **Rate limit**: aplica por principal y por canal; agrega circuit-breakers.
8. **Approvals**: para herramientas de side effects (write) exige approvals + 2FA.
9. **Backups**: snapshot/backup cifrado de SQLite o usa Postgres en prod.
