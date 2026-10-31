import { useEffect, useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { Alert, Avatar, Box, Button, Card, CardContent, Stack, Typography } from '@mui/material';
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
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'var(--bg)', p: 3 }}>
      <Card sx={{ width: '100%', maxWidth: 384 }}>
        <CardContent sx={{ p: 4 }}>
          <Stack spacing={2.5}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
              <Avatar variant="rounded" sx={{ bgcolor: 'var(--accent)', color: 'var(--bg)', fontWeight: 700 }}>D</Avatar>
              <Typography sx={{ fontSize: 24, fontWeight: 700 }}>Drivly</Typography>
            </Stack>
            <Box>
              <Typography variant="h1" sx={{ fontSize: 20 }}>Portal de garajes</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>Para administradores. Conductores y playeros usan la app de Drivly.</Typography>
            </Box>
            {HAS_GOOGLE && !USE_MOCKS && (
              <GoogleLogin onSuccess={(r) => handle(r.credential)} onError={() => setError('No se pudo iniciar sesión con Google.')} locale="es" width="320" theme="filled_black" />
            )}
            {(USE_MOCKS || import.meta.env.DEV) && (
              <Button variant="outlined" onClick={() => handle('demo')} disabled={busy}>{busy ? 'Ingresando…' : 'Acceso rápido de desarrollo'}</Button>
            )}
            {error && <Alert severity="error">{error}</Alert>}
          </Stack>
        </CardContent>
      </Card>
    </Box>
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
  return <AdminPortalView user={user} />;
}
