services:
  app:
    image: ${service_image}
    container_name: swiftdeploy-app
    user: "10001:10001"
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    environment:
      MODE: ${service_mode}
      APP_VERSION: ${app_version}
      APP_PORT: "${service_port}"
    expose:
      - "${service_port}"
    networks:
      - swiftdeploy
    restart: ${restart_policy}
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${service_port}/healthz', timeout=2).read()"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 5s

  nginx:
    image: ${nginx_image}
    container_name: swiftdeploy-nginx
    user: "101:101"
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    depends_on:
      app:
        condition: service_healthy
    ports:
      - "${nginx_port}:${nginx_port}"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - swiftdeploy-logs:/tmp/swiftdeploy-logs
    networks:
      - swiftdeploy
    restart: ${restart_policy}

networks:
  swiftdeploy:
    name: ${network_name}
    driver: ${network_driver}

volumes:
  swiftdeploy-logs:
    name: swiftdeploy-logs
