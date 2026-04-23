import { useEffect, useState } from "react";
import type { Session } from "../api/sessions";

interface Props {
  session: Session;
  onTerminate: (id: string) => void;
}

function statusBadge(status: Session["status"]) {
  const map: Record<Session["status"], { label: string; cls: string }> = {
    pending: { label: "Provisioning", cls: "badge badge-pending" },
    running: { label: "Running", cls: "badge badge-running" },
    failed: { label: "Failed", cls: "badge badge-failed" },
    terminated: { label: "Terminated", cls: "badge badge-terminated" },
  };
  const b = map[status];
  return <span className={b.cls}>{b.label}</span>;
}

function formatTimeRemaining(expiresAt: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now();
  if (diff <= 0) return "Expired";
  const hours = Math.floor(diff / 3_600_000);
  const minutes = Math.floor((diff % 3_600_000) / 60_000);
  if (hours > 0) return `${hours}h ${minutes}m remaining`;
  return `${minutes}m remaining`;
}

export default function SessionCard({ session, onTerminate }: Props) {
  const [timeLeft, setTimeLeft] = useState(() =>
    formatTimeRemaining(session.expires_at)
  );

  useEffect(() => {
    const interval = setInterval(() => {
      setTimeLeft(formatTimeRemaining(session.expires_at));
    }, 30_000);
    return () => clearInterval(interval);
  }, [session.expires_at]);

  const createdAt = new Date(session.created_at).toLocaleString();

  return (
    <div className="session-card">
      <div className="session-card-header">
        <code className="session-id">{session.id}</code>
        {statusBadge(session.status)}
      </div>
      <div className="session-card-body">
        <p>
          <strong>Created:</strong> {createdAt}
        </p>
        <p>
          <strong>TTL:</strong>{" "}
          <span className={timeLeft === "Expired" ? "text-danger" : "text-muted"}>
            {timeLeft}
          </span>
        </p>
        {session.access_url && session.status === "running" && (
          <a
            href={session.access_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-link"
          >
            Open Application
          </a>
        )}
        {session.status === "pending" && (
          <p className="muted">Waiting for pod to become ready...</p>
        )}
      </div>
      <div className="session-card-footer">
        <button
          className="btn btn-danger"
          onClick={() => onTerminate(session.id)}
          disabled={session.status === "terminated"}
        >
          Terminate
        </button>
      </div>
    </div>
  );
}
