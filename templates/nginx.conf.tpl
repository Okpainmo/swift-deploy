worker_processes auto;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    client_body_temp_path /tmp/client_temp;
    proxy_temp_path /tmp/proxy_temp;
    fastcgi_temp_path /tmp/fastcgi_temp;
    uwsgi_temp_path /tmp/uwsgi_temp;
    scgi_temp_path /tmp/scgi_temp;

    log_format swiftdeploy '$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request';
    access_log /dev/stdout swiftdeploy;
    error_log /dev/stderr warn;

    upstream swiftdeploy_app {
        server swiftdeploy-app:${service_port};
    }

    server {
        listen ${nginx_port};
        server_name _;

        proxy_connect_timeout ${proxy_timeout};
        proxy_send_timeout ${proxy_timeout};
        proxy_read_timeout ${proxy_timeout};

        error_page 502 = @error_502;
        error_page 503 = @error_503;
        error_page 504 = @error_504;

        location / {
            proxy_pass http://swiftdeploy_app;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_hide_header X-Mode;
            add_header X-Deployed-By swiftdeploy always;
            add_header X-Mode $upstream_http_x_mode always;
        }

        location @error_502 {
            internal;
            default_type application/json;
            add_header X-Deployed-By swiftdeploy always;
            return 502 '{"error":"bad gateway","code":"502","service":"swiftdeploy-app","contact":"${contact}"}';
        }

        location @error_503 {
            internal;
            default_type application/json;
            add_header X-Deployed-By swiftdeploy always;
            return 503 '{"error":"service unavailable","code":"503","service":"swiftdeploy-app","contact":"${contact}"}';
        }

        location @error_504 {
            internal;
            default_type application/json;
            add_header X-Deployed-By swiftdeploy always;
            return 504 '{"error":"gateway timeout","code":"504","service":"swiftdeploy-app","contact":"${contact}"}';
        }
    }
}
