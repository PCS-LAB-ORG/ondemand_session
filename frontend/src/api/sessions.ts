export interface Session {
  id: string;
  user_id: string;
  session_name: string;
  status: "pending" | "running" | "failed" | "terminated";
  created_at: string;
  expires_at: string;
  access_url: string | null;
}

export interface SessionListResponse {
  sessions: Session[];
}

function getDeviceId(): string {
  let id = localStorage.getItem("ondemand_device_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("ondemand_device_id", id);
  }
  return id;
}

const headers = (sessionName: string) => ({
  "Content-Type": "application/json",
  "X-Device-Id": getDeviceId(),
  "X-Session-Name": sessionName,
});

export async function claimSessionName(
  sessionName: string
): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch("/api/auth/claim", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Device-Id": getDeviceId(),
    },
    body: JSON.stringify({ session_name: sessionName }),
  });
  if (res.status === 409) {
    return { ok: false, error: "Session name already exists" };
  }
  if (!res.ok) {
    return { ok: false, error: "Failed to claim session name" };
  }
  return { ok: true };
}

export async function createSession(
  sessionName: string
): Promise<Session> {
  const res = await fetch("/api/sessions", {
    method: "POST",
    headers: headers(sessionName),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to create session: ${detail}`);
  }
  return res.json();
}

export async function listSessions(
  sessionName: string
): Promise<SessionListResponse> {
  const res = await fetch("/api/sessions", {
    headers: headers(sessionName),
  });
  if (!res.ok) throw new Error("Failed to list sessions");
  return res.json();
}

export async function getSession(
  sessionName: string,
  sessionId: string
): Promise<Session> {
  const res = await fetch(`/api/sessions/${sessionId}`, {
    headers: headers(sessionName),
  });
  if (!res.ok) throw new Error("Failed to get session");
  return res.json();
}

export async function deleteSession(
  sessionName: string,
  sessionId: string
): Promise<void> {
  const res = await fetch(`/api/sessions/${sessionId}`, {
    method: "DELETE",
    headers: headers(sessionName),
  });
  if (!res.ok) throw new Error("Failed to delete session");
}
