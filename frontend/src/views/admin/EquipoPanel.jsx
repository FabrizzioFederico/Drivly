import { useEffect, useState } from 'react';
import {
  Avatar, Box, Button, Card, Chip, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { garajesService } from '../../api/garajesService';
import { Aviso, Encabezado, Seccion } from './comun';

/** C4 · Equipo — Playeros (RFW-06) */
export default function EquipoPanel({ garajeId }) {
  const [playeros, setPlayeros] = useState(null);
  const [form, setForm] = useState({ email: '', nombre: '' });
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = () =>
    garajesService.getPlayeros(garajeId)
      .then(setPlayeros)
      .catch((e) => setMsg({ ok: false, text: e.message }));

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [garajeId]);

  const agregar = async (e) => {
    e.preventDefault();
    setAdding(true); setMsg(null);
    try {
      await garajesService.addPlayero(garajeId, form);
      setForm({ email: '', nombre: '' });
      await load();
      setMsg({ ok: true, text: 'Playero agregado. Entra desde la app de Drivly con Google, usando ese email.' });
    } catch (err) {
      setMsg({ ok: false, text: err.fields?.email?.[0] ?? err.message });
    } finally { setAdding(false); }
  };

  const quitar = async (usuarioId) => {
    try {
      await garajesService.removePlayero(garajeId, usuarioId);
      setPlayeros((ps) => ps.filter((p) => p.id !== usuarioId));
    } catch (e) { setMsg({ ok: false, text: e.message }); }
  };

  return (
    <>
      <Encabezado titulo="Equipo" detalle="Los playeros entran a la app con Google usando el email registrado aquí." />
      <Aviso msg={msg} />

      <Seccion titulo="Agregar playero" sx={{ maxWidth: 760 }}>
        <Box component="form" onSubmit={agregar} sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr auto' } }}>
          <TextField required type="email" size="small" label="Email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
          <TextField size="small" label="Nombre (opcional)" value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} />
          <Button type="submit" variant="contained" color="secondary" disabled={adding || !form.email}>{adding ? '…' : 'Agregar'}</Button>
        </Box>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>Si el playero ya tiene cuenta en Drivly sin garaje asignado, se le reasigna este garaje automáticamente.</Typography>
      </Seccion>

      <Card>
        <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', px: 3, py: 2 }}>
          <Typography variant="h2">Miembros del equipo</Typography>
          {playeros && <Typography variant="body2" sx={{ color: 'text.secondary' }}>{playeros.length} {playeros.length === 1 ? 'playero' : 'playeros'}</Typography>}
        </Stack>
        {!playeros ? (
          <Stack spacing={1} sx={{ px: 3, pb: 3 }}>{[0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={56} />)}</Stack>
        ) : playeros.length === 0 ? (
          <Typography variant="body2" sx={{ color: 'text.secondary', px: 3, pb: 3 }}>No hay playeros registrados en este garaje.</Typography>
        ) : (
          <TableContainer>
            <Table sx={{ minWidth: 560 }}>
              <TableHead>
                <TableRow><TableCell>Nombre</TableCell><TableCell>Email</TableCell><TableCell>Estado</TableCell><TableCell /></TableRow>
              </TableHead>
              <TableBody>
                {playeros.map((p) => (
                  <TableRow key={p.id} hover>
                    <TableCell>
                      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                        <Avatar sx={{ width: 32, height: 32, fontSize: 13, fontWeight: 700, bgcolor: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>{(p.nombre || p.email).slice(0, 2).toUpperCase()}</Avatar>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{p.nombre || '—'}</Typography>
                      </Stack>
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{p.email}</TableCell>
                    <TableCell><Chip size="small" label={p.is_active ? 'Activo' : 'Inactivo'} color={p.is_active ? 'success' : 'default'} variant="outlined" sx={{ fontWeight: 700 }} /></TableCell>
                    <TableCell align="right"><Button color="error" size="small" onClick={() => quitar(p.id)}>Quitar</Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Card>
    </>
  );
}
