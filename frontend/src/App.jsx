import { useEffect, useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { authService } from './api/authService';
import { USE_MOCKS } from './api/client';
import AdminPortalView from './views/AdminPortalView';

const HAS_GOOGLE = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID);

function Login({ onLogin }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const handle = async (credential) => {
    setBusy(true); setError(null);
    try { onLogin(await authService.loginWithGoogle(credential)); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-ink p-6">
      <div className="card flex w-full max-w-sm flex-col gap-5 p-8">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-card bg-brand text-xl font-extrabold text-white">D</span>
          <span className="text-2xl font-extrabold">Drivly</span>
        </div>
        <div><h1 className="text-xl font-extrabold">Portal de garajes</h1><p className="text-sm text-ink-muted">Para administradores. Conductores y playeros usan la app de Drivly.</p></div>
        {HAS_GOOGLE && !USE_MOCKS && (
          <GoogleLogin onSuccess={(r) => handle(r.credential)} onError={() => setError('No se pudo iniciar sesión con Google.')} locale="es" width="320" />
        )}
        {(USE_MOCKS || import.meta.env.DEV) && (
          <button onClick={() => handle('demo')} disabled={busy} className="btn-outline">{busy ? 'Ingresando…' : 'Acceso rápido de desarrollo'}</button>
        )}
        {error && <p role="alert" className="text-sm font-semibold text-debt-ink">{error}</p>}
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(() => authService.sesionGuardada());

  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener('drivly:logout', onLogout);
    return () => window.removeEventListener('drivly:logout', onLogout);
  }, []);

  if (!user) return <Login onLogin={setUser} />;

  return (
    <div className="flex min-h-full flex-col bg-[#E6E9EE]">
      <header className="sticky top-0 z-40 flex flex-wrap items-center justify-between gap-3 bg-ink px-4 py-3 text-white">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-brand font-extrabold">D</span>
          <span className="font-extrabold">Drivly</span>
          {USE_MOCKS && <span className="rounded-full bg-hold/15 px-2.5 py-1 text-[11px] font-bold text-hold">DATOS SIMULADOS</span>}
        </div>
        <button onClick={() => authService.logout()} className="min-h-touch rounded-card px-3 text-sm font-semibold text-ink-subtle hover:text-white">Salir</button>
      </header>
      <main className="flex-1 p-3 sm:p-6">
        <AdminPortalView user={user} />
      </main>
    </div>
  );
}
