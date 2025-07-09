# Pylon


## Reverse Proxy Client
Pylon can be configured to work with a reverse proxy client, to allow external access to the Pai cluster. This is useful for scenarios where you want to expose the Pylon service to the outside world, while keeping the internal cluster network secure. 

To make the client work, you should set the `reverse_proxy` section in the Pylon configuration of Cluster configuration. You also need to set up a reverse proxy server that will forward requests to the Pylon service running on the Pai cluster.


#### Configuration of Pylon

The following is an example configuration for Pylon with reverse proxy client. Details can be found in the [Pylon configuration documentation](./config/pylon.md).

```yaml
pylon:
  port: 80
  domain: auto-test.openpai.org
  ssl:
    crt_name: openpai.org.fullchain.pem
    crt_path: /tmp/auth-configuration/openpai.org.fullchain.pem
    key_name: openpai.org.privkey.pem
    key_path: /tmp/auth-configuration/openpai.org.privkey.pem
  reverse-proxy:
    server_addr: gateway.openpai.org
    server_port: 50111
    server_token: XXXXXXX
    binded_port: 50001
```

#### Reverse Proxy Server

Besides the Pylon configuration, you also need to set up a reverse proxy server that will forward requests to the Pylon service running on the Pai cluster.

The following is an example reverse proxy server configuration:

```yaml
bindPort: 50111
proxyBindAddr: "127.0.0.1"
auth:
  method: token
  token: < your_token_here >
```

You can also set up a Nginx server to work with this reverse proxy server to handle SSL termination and other features. Below is an example Nginx configuration that works with the reverse proxy server:

```nginx

server {
    listen 443 ssl http2;  # Listen on HTTPS with HTTP/2 support
    listen [::]:443 ssl http2;  # IPv6 support
    server_name gateway.openpai.org;

    # SSL Certificate files
    ssl_certificate < ssl full chain path >;  # Full chain of your certificate
    ssl_certificate_key < ssl private key path >;  # Private key of your certificate

    # SSL settings for enhanced security
    ssl_protocols TLSv1.2 TLSv1.3;  # Modern protocols only
    ssl_prefer_server_ciphers on;
    ssl_ciphers "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256";
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1h;

    # Define the resolver for DNS lookups
    resolver 8.8.8.8 1.1.1.1 valid=30s;
    resolver_timeout 10s;

    # Proxy rules for auto-test cluster
    location ~ ^/auto-test/job-server/.*$ {
        # Remove "/auto-test" prefix and retain the rest of the path
        rewrite ^/auto-test/job-server/(.*)$ /job-server/$1 break;

        # Proxy to the internal frp port for auto-test cluster
        proxy_pass https://localhost:50001;  # Adjust the port as needed
        proxy_set_header Host auto-test.openpai.org;  # Preserve original host header
        proxy_set_header X-Real-IP $remote_addr;  # Forward client IP
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_ssl_verify off;  # Disable SSL verification if auto-test uses self-signed certificate
    }

    # Optional: Root path behavior
    location = / {
        return 404;  # Serve 404 or any custom message
    }

    # Logging
    error_log /var/log/nginx/gateway_error.log;
    access_log /var/log/nginx/gateway_access.log;
}

# Redirect HTTP traffic to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name gateway.openpai.org;

    return 301 https://$host$request_uri;
}
```

This nginx configuration listens on port 443 for HTTPS traffic, handles SSL termination, and proxies requests to the Pylon service running on the Pai cluster. It only forwards requests that match the `https://gateway.openpai.org/auto-test/job-server/{path}` path to reverse proxy server running on port 50001, which will be forwarded to the Pylon service of the auto-test cluster `https://auto-test.openpai.org/job-server/{path}`.

**Note:** Make sure that the pai-master node can access the reverse proxy server. You should add access rules to the reverse proxy server to allow requests from the pai-master node. 