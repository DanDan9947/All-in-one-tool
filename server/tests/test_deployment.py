from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_nginx_serves_vue_history_routes_and_proxies_api():
    config = (PROJECT_ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    assert "root /usr/share/nginx/html;" in config
    assert "try_files $uri $uri/ /index.html;" in config
    assert "location /api/" in config
    assert "proxy_pass http://api:8000;" in config


def test_compose_builds_the_web_nginx_image():
    compose = (PROJECT_ROOT / "deploy" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    dockerfile = (PROJECT_ROOT / "deploy" / "web.Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "dockerfile: deploy/web.Dockerfile" in compose
    assert "RUN npm run build" in dockerfile
    assert "/usr/share/nginx/html" in dockerfile
