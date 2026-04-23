import { useCallback, useEffect, useRef, useState } from "react";
import {
  claimSessionName,
  createSession,
  deleteSession,
  listSessions,
  type Session,
} from "./api/sessions";
import CreateSession from "./components/CreateSession";
import SessionList from "./components/SessionList";
import "./index.css";

const POLL_INTERVAL = 3000;

export default function App() {
  const [sessionName, setSessionName] = useState(() => {
    return localStorage.getItem("ondemand_session_name") || "";
  });
  const [loggedIn, setLoggedIn] = useState(() => {
    return !!localStorage.getItem("ondemand_session_name");
  });
  const [sessions, setSessions] = useState<Session[]>([]);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSessions = useCallback(async () => {
    if (!loggedIn) return;
    try {
      const data = await listSessions(sessionName);
      setSessions(data.sessions);
    } catch {
      /* swallow polling errors */
    }
  }, [sessionName, loggedIn]);

  useEffect(() => {
    if (!loggedIn) return;
    fetchSessions();
    pollRef.current = setInterval(fetchSessions, POLL_INTERVAL);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loggedIn, fetchSessions]);

  const handleLogin = async () => {
    const trimmed = sessionName.trim();
    if (!trimmed) return;
    setLoginError(null);

    const result = await claimSessionName(trimmed);
    if (!result.ok) {
      setLoginError(result.error || "Session name already exists");
      return;
    }

    localStorage.setItem("ondemand_session_name", trimmed);
    setSessionName(trimmed);
    setLoggedIn(true);
  };

  const handleLogout = () => {
    localStorage.removeItem("ondemand_session_name");
    setLoggedIn(false);
    setSessionName("");
    setSessions([]);
    setError(null);
    setLoginError(null);
  };

  const handleLaunch = async () => {
    setLaunching(true);
    setError(null);
    try {
      await createSession(sessionName);
      await fetchSessions();
    } catch (e: any) {
      setError(e.message || "Failed to launch session");
    } finally {
      setLaunching(false);
    }
  };

  const handleTerminate = async (sessionId: string) => {
    setError(null);
    try {
      await deleteSession(sessionName, sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (e: any) {
      setError(e.message || "Failed to terminate session");
    }
  };

  if (!loggedIn) {
    return (
      <div className="app">
        <div className="login-card">
          <h1>On-Demand Sessions</h1>
          <p>Enter a session name to get started.</p>
          <div className="login-form">
            <input
              type="text"
              placeholder="Session name"
              value={sessionName}
              onChange={(e) => {
                setSessionName(e.target.value);
                setLoginError(null);
              }}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
            <button className="btn btn-primary" onClick={handleLogin}>
              Continue
            </button>
          </div>
          {loginError && (
            <div className="login-error">{loginError}</div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>On-Demand Sessions</h1>
        <div className="user-info">
          <span>
            Session: <strong>{sessionName}</strong>
          </span>
          <button className="btn btn-text" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="app-main">
        <CreateSession onLaunch={handleLaunch} disabled={launching} />
        {error && <div className="error-banner">{error}</div>}
        <SessionList sessions={sessions} onTerminate={handleTerminate} />
      </main>
    </div>
  );
}
