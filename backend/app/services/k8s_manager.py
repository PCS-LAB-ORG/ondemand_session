from __future__ import annotations

import json
import logging
import subprocess
import textwrap

from app.config import settings

logger = logging.getLogger(__name__)

_creds_fetched = False


def _run(cmd: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def _ensure_credentials() -> None:
    """Fetch GKE credentials via gcloud once per process lifetime."""
    global _creds_fetched
    if _creds_fetched:
        return
    if not settings.gcp_project or not settings.gcp_cluster or not settings.gcp_zone:
        logger.warning("GCP credentials not configured, skipping gcloud get-credentials")
        _creds_fetched = True
        return
    _run([
        "gcloud", "container", "clusters", "get-credentials",
        settings.gcp_cluster,
        "--zone", settings.gcp_zone,
        "--project", settings.gcp_project,
    ])
    logger.info(
        "Fetched GKE credentials for %s/%s/%s",
        settings.gcp_project, settings.gcp_zone, settings.gcp_cluster,
    )
    _creds_fetched = True


def _kubectl(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    _ensure_credentials()
    return _run(["kubectl"] + args, check=check)


def _kubectl_apply(yaml: str) -> subprocess.CompletedProcess:
    _ensure_credentials()
    logger.debug("Applying YAML:\n%s", yaml)
    return subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=yaml, check=True, capture_output=True, text=True,
    )


def _pod_name(session_id: str) -> str:
    return f"session-{session_id}"


def _service_name(session_id: str) -> str:
    return f"session-{session_id}"


def _ingress_name(session_id: str) -> str:
    return f"ingress-{session_id}"


def _session_host(session_name: str) -> str:
    return f"{session_name}.{settings.session_domain}"


def create_session_pod(session_id: str) -> str:
    """Create a stateless Pod with a TTL via kubectl. Returns the pod name."""
    pod_name = _pod_name(session_id)
    ttl_seconds = settings.session_ttl_hours * 3600

    yaml = textwrap.dedent(f"""\
        apiVersion: v1
        kind: Pod
        metadata:
          name: {pod_name}
          namespace: {settings.session_namespace}
          labels:
            app: user-session
            session-id: "{session_id}"
            managed-by: ondemand-session
        spec:
          activeDeadlineSeconds: {ttl_seconds}
          restartPolicy: Never
          containers:
            - name: app
              image: {settings.session_image}
              ports:
                - containerPort: {settings.session_port}
              resources:
                requests:
                  cpu: {settings.session_cpu_request}
                  memory: {settings.session_memory_request}
                limits:
                  cpu: {settings.session_cpu_limit}
                  memory: {settings.session_memory_limit}
              volumeMounts:
                - name: scratch
                  mountPath: /tmp
                - name: workspace
                  mountPath: /workspace
          volumes:
            - name: scratch
              emptyDir: {{}}
            - name: workspace
              emptyDir: {{}}
    """)
    _kubectl_apply(yaml)
    logger.info("Created pod %s (TTL=%ds)", pod_name, ttl_seconds)
    return pod_name


def create_session_service(session_id: str) -> str:
    """Create a ClusterIP Service targeting the session pod. Returns service name."""
    svc_name = _service_name(session_id)

    yaml = textwrap.dedent(f"""\
        apiVersion: v1
        kind: Service
        metadata:
          name: {svc_name}
          namespace: {settings.session_namespace}
          labels:
            app: user-session
            session-id: "{session_id}"
            managed-by: ondemand-session
        spec:
          selector:
            app: user-session
            session-id: "{session_id}"
          ports:
            - port: 80
              targetPort: {settings.session_port}
              protocol: TCP
          type: ClusterIP
    """)
    _kubectl_apply(yaml)
    logger.info("Created service %s", svc_name)
    return svc_name


def create_session_ingress(session_id: str, session_name: str) -> str:
    """Create an Ingress with a host rule for subdomain routing. Returns the access URL."""
    ingress_name = _ingress_name(session_id)
    svc_name = _service_name(session_id)
    host = _session_host(session_name)

    yaml = textwrap.dedent(f"""\
        apiVersion: networking.k8s.io/v1
        kind: Ingress
        metadata:
          name: {ingress_name}
          namespace: {settings.session_namespace}
          labels:
            app: user-session
            session-id: "{session_id}"
            managed-by: ondemand-session
        spec:
          ingressClassName: nginx
          rules:
            - host: {host}
              http:
                paths:
                  - path: /
                    pathType: Prefix
                    backend:
                      service:
                        name: {svc_name}
                        port:
                          number: 80
    """)
    _kubectl_apply(yaml)
    access_url = f"https://{host}"
    logger.info("Created ingress %s -> %s", ingress_name, access_url)
    return access_url


def get_pod_status(session_id: str) -> str | None:
    """Return pod phase via kubectl, or None if not found."""
    pod_name = _pod_name(session_id)
    result = _kubectl(
        [
            "get", "pod", pod_name,
            "-n", settings.session_namespace,
            "-o", "jsonpath={.status.phase}",
        ],
        check=False,
    )
    if result.returncode != 0:
        return None
    phase = result.stdout.strip()
    return phase if phase else None


def delete_session_resources(session_id: str) -> None:
    """Delete pod, service, and ingress for a session via kubectl."""
    pod_name = _pod_name(session_id)
    svc_name = _service_name(session_id)
    ingress_name = _ingress_name(session_id)
    ns = settings.session_namespace

    for kind, name in [("pod", pod_name), ("service", svc_name), ("ingress", ingress_name)]:
        result = _kubectl(
            ["delete", kind, name, "-n", ns, "--ignore-not-found=true"],
            check=False,
        )
        if result.returncode == 0:
            logger.info("Deleted %s/%s", kind, name)
        else:
            logger.warning("Failed to delete %s/%s: %s", kind, name, result.stderr.strip())
