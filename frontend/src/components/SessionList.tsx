import type { Session } from "../api/sessions";
import SessionCard from "./SessionCard";

interface Props {
  sessions: Session[];
  onTerminate: (id: string) => void;
}

export default function SessionList({ sessions, onTerminate }: Props) {
  if (sessions.length === 0) {
    return (
      <div className="empty-state">
        <p>No active sessions. Launch one to get started.</p>
      </div>
    );
  }

  return (
    <div className="session-list">
      {sessions.map((s) => (
        <SessionCard key={s.id} session={s} onTerminate={onTerminate} />
      ))}
    </div>
  );
}
