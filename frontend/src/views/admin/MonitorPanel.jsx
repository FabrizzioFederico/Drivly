import { useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, Card, Chip, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import { garajesService } from '../../api/garajesService';
import { reservasService } from '../../api/reservasService';
import StatusBadge from '../../components/StatusBadge';
import VehiclePlateBadge, { formatPatente } from '../../components/VehiclePlateBadge';
import { descargarExcel } from '../../lib/excel';
import { ars, CATEGORIA_LABEL, hora } from '../../lib/format';
import { MONO } from '../../theme';
import { Encabezado, Leyenda, Seccion } from './comun';

const FILTROS = ['TODOS', 'HOLD', 'CONFIRMADA', 'EN_CURSO', 'CON_DEUDA', 'SIN_LUGAR'];
const COLUMNAS = ['ID reserva', 'Patente', 'Categoría', 'Tipo', 'Horario', 'Estado', 'Importe'];
const ALTO_GRAFICO = 220;

// Para el Excel: los mismos nombres que el backend (reservas/models.py)
const ORIGEN_LABEL = { APP: 'App', PRESENCIAL: 'Presencial' };
const MODALIDAD_LABEL = { HORA: 'Por hora', SEMANAL: 'Abono semanal', MENSUAL: 'Abono mensual', ANUAL: 'Abono anual', PRESENCIAL: 'Cliente sin reserva' };
const ESTADO_LABEL = {
  HOLD: 'Retenida (esperando pago)', CONFIRMADA: 'Confirmada', EN_CURSO: 'En curso', FINALIZADA: 'Finalizada', CON_DEUDA: 'Con deuda',
  EXPIRADA: 'Expirada', CANCELADA: 'Cancelada', NO_SHOW: 'No se presentó', SIN_LUGAR: 'Sin lugar físico',
};

const tipo = (r) => (r.origen !== 'APP' ? 'Sin reserva' : r.modalidad && r.modalidad !== 'HORA' ? `Abono ${r.modalidad.toLowerCase()}` : 'App');
const horario = (r) => (r.modalidad && !['HORA', 'PRESENCIAL'].includes(r.modalidad) ? `hasta ${new Date(r.fin).toLocaleDateString('es-AR')}` : `${hora(r.inicio)}–${hora(r.fin)}`);

function Grafico({ ocupacion }) {
  const total = ocupacion?.capacidad ?? 80;
  const umbral = Math.round(total * (ocupacion?.umbral_alerta ?? 0.9));
  const H = ALTO_GRAFICO;
  const nowH = new Date().getHours();
  const franjas = ocupacion?.franjas ?? [];
  const columnas = `repeat(${franjas.length || 18}, minmax(0, 1fr))`;

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <Box sx={{ minWidth: 640 }}>
        <Box sx={{ position: 'relative', display: 'grid', alignItems: 'end', gap: 1, height: H, gridTemplateColumns: columnas, borderBottom: 1.5, borderColor: 'divider' }}>
          <Box sx={{ position: 'absolute', left: 0, right: 0, bottom: (umbral / total) * H, borderTop: '2px dashed var(--warning)' }} />
          <Typography variant="caption" sx={{ color: 'warning.main', position: 'absolute', right: 0, bottom: (umbral / total) * H + 2, bgcolor: 'background.paper', pl: 0.75, fontWeight: 700 }}>{umbral} / {total}</Typography>
          {franjas.map((f) => {
            const over = f.app + f.presencial >= umbral;
            return (
              <Tooltip key={f.hora} arrow title={`${f.hora}:00 · App y abonos ${f.app} · Sin reserva ${f.presencial}${over ? ' · ⚠' : ''}`}>
                <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: '2px', opacity: f.proyectada ? 0.45 : 1 }}>
                  <Box sx={{ height: (f.presencial / total) * H, bgcolor: 'var(--text-muted)', borderRadius: '4px 4px 0 0' }} />
                  <Box sx={{ height: (f.app / total) * H, bgcolor: 'primary.main', ...(f.hora === nowH ? { outline: '2px solid var(--text-primary)', outlineOffset: 2 } : {}) }} />
                </Box>
              </Tooltip>
            );
          })}
        </Box>
        <Box sx={{ display: 'grid', gap: 1, gridTemplateColumns: columnas, mt: 1 }}>
          {franjas.map((f) => (
            <Typography key={f.hora} variant="caption" sx={{ textAlign: 'center', fontFamily: MONO, fontWeight: f.hora === nowH ? 800 : 400, color: f.hora === nowH ? 'text.primary' : 'text.secondary' }}>
              {String(f.hora).padStart(2, '0')}
            </Typography>
          ))}
        </Box>
      </Box>
    </Box>
  );
}

/** C2 · Monitor en vivo y reportes (CU-10) */
export default function MonitorPanel({ garajeId }) {
  const [ocupacion, setOcupacion] = useState(null);
  const [reservas, setReservas] = useState([]);
  const [filtro, setFiltro] = useState('TODOS');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () => garajesService.ocupacion(garajeId).then(setOcupacion).catch(() => {});
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [garajeId]);

  useEffect(() => {
    setLoading(true);
    reservasService.list({ garaje: garajeId }).then(setReservas).finally(() => setLoading(false));
  }, [garajeId]);

  const counts = useMemo(() => FILTROS.reduce((acc, f) => ({ ...acc, [f]: f === 'TODOS' ? reservas.length : reservas.filter((r) => r.estado === f).length }), {}), [reservas]);
  const filtradas = filtro === 'TODOS' ? reservas : reservas.filter((r) => r.estado === filtro);
  const alertas = ocupacion?.alertas_overstay ?? [];

  const exportar = () => descargarExcel(`drivly-reservas-${filtro.toLowerCase()}-${new Date().toLocaleDateString('en-CA')}.xlsx`, 'Reservas', filtradas, [
    { label: 'ID', value: (r) => String(r.id).slice(0, 8), ancho: 12 },
    { label: 'Patente', value: (r) => r.patente, ancho: 12 },
    { label: 'Categoría', value: (r) => CATEGORIA_LABEL[r.categoria] ?? r.categoria, ancho: 13 },
    { label: 'Origen', value: (r) => ORIGEN_LABEL[r.origen] ?? r.origen, ancho: 12 },
    { label: 'Modalidad', value: (r) => MODALIDAD_LABEL[r.modalidad] ?? r.modalidad, ancho: 20 },
    { label: 'Inicio', value: (r) => r.inicio, tipo: 'fecha', ancho: 18 },
    { label: 'Fin', value: (r) => r.fin, tipo: 'fecha', ancho: 18 },
    { label: 'Estado', value: (r) => ESTADO_LABEL[r.estado] ?? r.estado, ancho: 26 },
    { label: 'Importe', value: (r) => r.total, tipo: 'importe', ancho: 16 },
  ]);

  return (
    <>
      <Encabezado titulo="Monitor de ocupación" detalle={new Date().toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' })}>
        <Chip label="En vivo" color="success" variant="outlined" sx={{ fontWeight: 800 }} />
      </Encabezado>

      {alertas.length > 0 && (
        <Alert severity="error">
          <Typography variant="body2" sx={{ fontWeight: 800 }}>Un vehículo excedido deja sin lugar a {alertas.length === 1 ? 'una reserva' : `${alertas.length} reservas`}</Typography>
          {alertas.map((a) => <div key={a.reserva_id}>{formatPatente(a.patente)} · llega a las {hora(a.inicio)}</div>)}
        </Alert>
      )}

      <Seccion
        titulo="Ocupación por franja horaria"
        detalle="Real hasta ahora · proyección según reservas confirmadas"
        accion={(
          <Stack direction="row" spacing={2}>
            <Leyenda color="primary.main">App y abonos</Leyenda>
            <Leyenda color="var(--text-muted)">Sin reserva</Leyenda>
            <Leyenda color="var(--warning)">Alerta {Math.round((ocupacion?.umbral_alerta ?? 0.9) * 100)}%</Leyenda>
          </Stack>
        )}
      >
        <Grafico ocupacion={ocupacion} />
      </Seccion>

      <Card>
        <Stack direction="row" sx={{ flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, px: 3, py: 2 }}>
          <Stack direction="row" sx={{ flexWrap: 'wrap', alignItems: 'center', gap: 1 }}>
            <Typography variant="h2" sx={{ mr: 1 }}>Reservas activas</Typography>
            {FILTROS.map((f) => (
              <Chip key={f} clickable label={`${f.replace('_', ' ')} ${counts[f]}`} onClick={() => setFiltro(f)} aria-pressed={filtro === f}
                color={filtro === f ? 'primary' : 'default'} variant={filtro === f ? 'filled' : 'outlined'} sx={{ fontWeight: 700 }} />
            ))}
          </Stack>
          <Button variant="outlined" onClick={exportar} disabled={!filtradas.length}>Exportar Excel</Button>
        </Stack>
        <TableContainer>
          <Table sx={{ minWidth: 820 }}>
            <TableHead>
              <TableRow>{COLUMNAS.map((c, i) => <TableCell key={c} align={i === 6 ? 'right' : 'left'}>{c}</TableCell>)}</TableRow>
            </TableHead>
            <TableBody>
              {loading && <TableRow><TableCell colSpan={7} sx={{ color: 'text.secondary' }}>Cargando reservas…</TableCell></TableRow>}
              {!loading && !filtradas.length && <TableRow><TableCell colSpan={7} sx={{ color: 'text.secondary' }}>No hay reservas con este estado.</TableCell></TableRow>}
              {filtradas.map((r) => (
                <TableRow key={r.id} hover>
                  <TableCell sx={{ fontFamily: MONO, fontSize: 13, color: 'text.secondary' }}>{r.id}</TableCell>
                  <TableCell><VehiclePlateBadge patente={r.patente} sinBorde /></TableCell>
                  <TableCell sx={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.05em' }}>{r.categoria}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: r.origen === 'APP' ? 'primary.main' : 'text.secondary' }}>{tipo(r)}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{horario(r)}</TableCell>
                  <TableCell><StatusBadge estado={r.estado} /></TableCell>
                  <TableCell align="right" sx={{ fontWeight: 800 }}>{ars(r.total)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </>
  );
}
