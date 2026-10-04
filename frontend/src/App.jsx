import { useEffect, useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { authService } from './api/authService';
import { USE_MOCKS } from './api/client';
import DriverAppView from './views/DriverAppView';
import ValetPortalView from './views/ValetPortalView';
import AdminPortalView from './views/AdminPortalView';

const ROLES = [
  { id: 'CONDUCTOR', label: 'Conductor', hint: 'App móvil' },
  { id: 'PLAYERO', label: 'Playero', hint: 'Móvil / tablet' },
  { id: 'ADMIN', label: 'Administrador', hint: 'Escritorio' },
];
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
        <div><h1 className="text-xl font-extrabold">Ingresá a tu cuenta</h1><p className="text-sm text-ink-muted">Conductores, playeros y administradores.</p></div>
        {HAS_GOOGLE && !USE_MOCKS ? (
          <GoogleLogin onSuccess={(r) => handle(r.credential)} onError={() => setError('No se pudo iniciar sesión con Google.')} locale="es" width="320" />
        ) : (
          <button onClick={() => handle('demo')} disabled={busy} className="btn-primary min-h-[52px]">{busy ? 'Ingresando…' : 'Entrar en modo demo'}</button>
        )}
        {error && <p role="alert" className="text-sm font-semibold text-debt-ink">{error}</p>}
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(() => (authService.isAuthenticated() ? authService.cachedUser() : null));
  const [role, setRole] = useState(() => localStorage.getItem('drivly.demoRole') || 'CONDUCTOR');

  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener('drivly:logout', onLogout);
    return () => window.removeEventListener('drivly:logout', onLogout);
  }, []);

  useEffect(() => { localStorage.setItem('drivly.demoRole', role); }, [role]);

  if (!user) return <Login onLogin={(u) => { setUser(u); if (u?.rol) setRole(u.rol); }} />;

  // En producción, el rol viene del JWT/perfil. El selector solo existe para demostración.
  const demoSelector = USE_MOCKS || user.rol === 'ADMIN';

  return (
    <div className="flex min-h-full flex-col bg-[#E6E9EE]">
      <header className="sticky top-0 z-40 flex flex-wrap items-center justify-between gap-3 bg-ink px-4 py-3 text-white">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-brand font-extrabold">D</span>
          <span className="font-extrabold">Drivly</span>
          {USE_MOCKS && <span className="rounded-full bg-hold/15 px-2.5 py-1 text-[11px] font-bold text-hold">DATOS SIMULADOS</span>}
        </div>
        {demoSelector && (
          <div className="flex gap-1 rounded-[14px] bg-ink-900 p-1" role="tablist" aria-label="Rol de demostración">
            {ROLES.map((r) => (
              <button key={r.id} role="tab" aria-selected={role === r.id} onClick={() => setRole(r.id)}
                className={`flex min-h-[44px] flex-col items-start justify-center rounded-[10px] px-3.5 text-left ${role === r.id ? 'bg-brand text-white' : 'text-ink-subtle hover:text-white'}`}>
                <span className="text-sm font-bold leading-tight">{r.label}</span>
                <span className="text-[10px] font-semibold opacity-80">{r.hint}</span>
              </button>
            ))}
          </div>
        )}
        <button onClick={() => authService.logout()} className="min-h-touch rounded-card px-3 text-sm font-semibold text-ink-subtle hover:text-white">Salir</button>
      </header>
      <main className="flex-1 p-3 sm:p-6">
        {role === 'CONDUCTOR' && <DriverAppView user={user} />}
        {role === 'PLAYERO' && <ValetPortalView user={user} />}
        {role === 'ADMIN' && <AdminPortalView user={user} />}
      </main>
    </div>
  );
}
