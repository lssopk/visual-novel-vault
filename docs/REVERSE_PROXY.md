# 反向代理示例（由你自行配置）

## Caddy

```caddy
vault.example.com {
    reverse_proxy 127.0.0.1:6099
    encode zstd gzip
}
```

## Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name vault.example.com;
    # SSL 证书、TLS 配置由你自己维护
    location / {
        proxy_pass http://127.0.0.1:6099;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 256k;
    }
}
```

站点初始仅绑定 `127.0.0.1:6099`。反代 HTTPS 配好后，在项目根目录 `.env` 写入 `PUBLIC_HTTPS=1` 并执行 `./deploy.sh`。建议额外启用 IP 白名单或 VPN、反向代理限流和定期备份。对于远程 Codex，确保其运行环境可访问 HTTPS 域名；若只允许本地访问，云端无法直接调用。
