import { useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Skeleton, Stack, TextField, Typography,
} from '@mui/material';
import { operacionService } from '../../api/operacionService';
import VehiclePlateBadge from '../../components/VehiclePlateBadge';
import { ars } from '../../lib/format';
import { Encabezado } from './comun';

function CondonarDialogo({ deuda, onHecho, onCancelar }) {
  const [motivo, setMotivo] = useState('');
  const [monto, setMonto] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const enviar = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await operacionService.condonar(deuda.reserva_id, { motivo: motivo.trim(), ...(monto ? { monto } : {}) });
      onHecho();
    } catch (err) { setError(err.message); setBusy(false); }
  };

  return (
    <Dialog open fullWidth maxWidth="xs" onClose={onCancelar}>
      <form onSubmit={enviar}>
        <DialogTitle>Condonar deuda de {deuda.patente}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField required autoFocus label="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: demora en la cola de salida" slotProps={{ htmlInput: { maxLength: 500 } }} />
            <TextField label="Monto a condonar" type="number" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder={ars(deuda.total)} helperText="Vacío = todo el saldo"
              slotProps={{ htmlInput: { min: 0.01, max: deuda.total, step: 0.01 } }} />
            {error && <Alert severity="error">{error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onCancelar}>Cancelar</Button>
          <Button type="submit" variant="contained" color="secondary" disabled={busy || !motivo.trim()}>{busy ? 'Guardando…' : 'Condonar'}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/** Deudas de overstay: reclamos y condonación (regla 4) */
export default function DeudasPanel({ garajeId }) {
  const [deudas, setDeudas] = useState(null);
  const [error, setError] = useState(null);
  const [condonando, setCondonando] = useState(null);

  const load = useMemo(() => () => operacionService.deudas(garajeId)
    .then((d) => { setDeudas(d); setError(null); })
    .catch((e) => { setDeudas([]); setError(e.message); }), [garajeId]);
  useEffect(() => { load(); }, [load]);

  return (
    <>
      <Encabezado titulo="Deudas" detalle="Overstays sin pagar. Si un conductor lo reclama, podés condonarlos total o parcialmente dejando el motivo." />
      {error && <Alert severity="error">{error}</Alert>}
      {deudas === null && <Skeleton variant="rounded" height={128} />}
      {deudas?.length === 0 && !error && <Card><CardContent><Typography variant="body2" sx={{ color: 'text.secondary' }}>No hay deudas pendientes.</Typography></CardContent></Card>}
      {deudas?.map((d) => (
        <Card key={d.reserva_id}>
          <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, '&:last-child': { pb: 2 } }}>
            <Stack direction="row" sx={{ flexWrap: 'wrap', alignItems: 'center', gap: 1.5 }}>
              <VehiclePlateBadge patente={d.patente} />
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>Salió {new Date(d.egreso_real).toLocaleDateString('es-AR')} · +{d.minutos_excedidos} min</Typography>
              {d.estado === 'INCOBRABLE' && <Chip size="small" color="error" label="INCOBRABLE" sx={{ fontWeight: 800 }} />}
              <Box sx={{ flexGrow: 1 }} />
              <Typography sx={{ fontSize: 20, fontWeight: 800 }}>{ars(d.total)}</Typography>
              <Button variant="outlined" onClick={() => setCondonando(d)}>Condonar</Button>
            </Stack>
            {Number(d.monto_condonado) > 0 && <Typography variant="body2" sx={{ color: 'text.secondary', whiteSpace: 'pre-line' }}>Ya condonado: {ars(d.monto_condonado)}. {d.motivo_condonacion}</Typography>}
          </CardContent>
        </Card>
      ))}
      {condonando && <CondonarDialogo deuda={condonando} onCancelar={() => setCondonando(null)} onHecho={() => { setCondonando(null); load(); }} />}
    </>
  );
}
