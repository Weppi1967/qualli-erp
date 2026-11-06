import { useEffect } from 'react';
import { HashRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { setSessionExpiredHandler } from './api/client';
import Layout from './components/Layout';
import { Spinner } from './components/ui';
import Dashboard from './pages/Dashboard';
import Enrollments from './pages/Enrollments';
import Import from './pages/Import';
import Login from './pages/Login';
import Measures from './pages/Measures';
import Participants from './pages/Participants';
import Settings from './pages/Settings';
import { useAuth } from './store/auth';

function RequireAuth({ children }) {
  const status = useAuth((s) => s.status);
  if (status === 'checking') return <Spinner label="Anmeldung wird geprüft…" />;
  if (status !== 'authenticated') return <Navigate to="/login" replace />;
  return children;
}

function SessionWatcher() {
  const navigate = useNavigate();
  const reset = useAuth((s) => s.reset);
  useEffect(() => {
    setSessionExpiredHandler(() => {
      reset();
      navigate('/login', { replace: true });
    });
  }, [navigate, reset]);
  return null;
}

export default function App() {
  const { status, loadMe } = useAuth();
  useEffect(() => {
    if (status === 'checking') loadMe().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <HashRouter>
      <SessionWatcher />
      <Routes>
        <Route path="/login" element={status === 'authenticated' ? <Navigate to="/" replace /> : <Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="teilnehmer" element={<Participants />} />
          <Route path="massnahmen" element={<Measures />} />
          <Route path="zuordnungen" element={<Enrollments />} />
          <Route path="import" element={<Import />} />
          <Route path="einstellungen" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
