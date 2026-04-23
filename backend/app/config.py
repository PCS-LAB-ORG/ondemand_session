from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # GCP cluster credentials
    gcp_project: str = ""
    gcp_cluster: str = ""
    gcp_zone: str = ""

    # Session pod settings
    session_namespace: str = "user-sessions"
    session_image: str = "nginx:latest"
    session_port: int = 80
    session_cpu_limit: str = "500m"
    session_memory_limit: str = "512Mi"
    session_cpu_request: str = "250m"
    session_memory_request: str = "256Mi"
    session_ttl_hours: int = 12

    # Subdomain routing: {session_name}.{session_domain}
    session_domain: str = "pcs.lab.twistlock.com"

    model_config = {"env_prefix": "ONDEMAND_"}


settings = Settings()
