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

const DEV_ROLES = [
  { rol: 'CONDUCTOR',    label: 'Conductor',      hint: 'App móvil' },
  { rol: 'ADMIN_GARAJE', label: 'Administrador',  hint: 'Panel web' },
  { rol: 'PLAYERO',      label: 'Playero',        hint: 'Escáner QR' },
];

function Login({ onLogin }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null); // null | rol string

  const handle = async (credential, rol) => {
    setBusy(rol ?? 'google'); setError(null);
    try { onLogin(await authService.loginWithGoogle(credential, rol)); }
    catch (e) { setError(e.message); } finally { setBusy(null); }
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-ink p-6">
      <div className="card flex w-full max-w-sm flex-col gap-5 p-8">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-card bg-brand text-xl font-extrabold text-white">D</span>
          <span className="text-2xl font-extrabold">Drivly</span>
        </div>
        <div><h1 className="text-xl font-extrabold">Ingresá a tu cuenta</h1><p className="text-sm text-ink-muted">Conductores, playeros y administradores.</p></div>
        {HAS_GOOGLE && !USE_MOCKS && (
          <GoogleLogin onSuccess={(r) => handle(r.credential, null)} onError={() => setError('No se pudo iniciar sesión con Google.')} locale="es" width="320" />
        )}
        {(USE_MOCKS || import.meta.env.DEV) && (
          <div className="flex flex-col gap-2">
            {HAS_GOOGLE && <p className="text-xs font-bold text-ink-muted">O acceso rápido de desarrollo:</p>}
            {DEV_ROLES.map(({ rol, label, hint }) => (
              <button key={rol} onClick={() => handle('demo', rol)} disabled={busy !== null}
                className={`flex items-center justify-between rounded-card border-[1.5px] px-4 py-3 text-left transition-colors ${busy === rol ? 'border-brand bg-brand/5' : 'border-ink-line bg-white hover:border-brand hover:bg-brand/5'}`}>
                <span className="text-sm font-bold">{label}</span>
                <span className="text-xs text-ink-muted">{busy === rol ? 'Ingresando…' : hint}</span>
              </button>
            ))}
          </div>
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

  // ADMIN_GARAJE del backend → tab 'ADMIN' del frontend
  const toTabRole = (r) => r === 'ADMIN_GARAJE' ? 'ADMIN' : r;

  if (!user) return <Login onLogin={(u) => { setUser(u); if (u?.rol) setRole(toTabRole(u.rol)); }} />;

  // En producción, el rol viene del JWT/perfil. El selector solo existe para demostración.
  const demoSelector = USE_MOCKS || import.meta.env.DEV || user.rol === 'ADMIN';

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
