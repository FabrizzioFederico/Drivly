import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert, Button, Card, Chip, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import { garajesService } from '../../api/garajesService';
import { reservasService } from '../../api/reservasService';
import StatusBadge from '../../components/StatusBadge';
import VehiclePlateBadge, { formatPatente } from '../../components/VehiclePlateBadge';
import { descargarExcel } from '../../lib/excel';
import { ars, CATEGORIA_LABEL, hora } from '../../lib/format';
import { useEnVivo } from '../../lib/useEnVivo';
import { MONO } from '../../theme';
import { Encabezado, Leyenda, Seccion } from './comun';
import GraficoOcupacion, { SERIE_APP, SERIE_PRESENCIAL } from './GraficoOcupacion';

const FILTROS = ['TODOS', 'HOLD', 'CONFIRMADA', 'EN_CURSO', 'CON_DEUDA', 'SIN_LUGAR'];
const COLUMNAS = ['ID reserva', 'Patente', 'Categoría', 'Tipo', 'Horario', 'Estado', 'Importe'];

// Para el Excel: los mismos nombres que el backend (reservas/models.py)
const ORIGEN_LABEL = { APP: 'App', PRESENCIAL: 'Presencial' };
const MODALIDAD_LABEL = { HORA: 'Por hora', SEMANAL: 'Abono semanal', MENSUAL: 'Abono mensual', ANUAL: 'Abono anual', PRESENCIAL: 'Cliente sin reserva' };
const ESTADO_LABEL = {
  HOLD: 'Retenida (esperando pago)', CONFIRMADA: 'Confirmada', EN_CURSO: 'En curso', FINALIZADA: 'Finalizada', CON_DEUDA: 'Con deuda',
  EXPIRADA: 'Expirada', CANCELADA: 'Cancelada', NO_SHOW: 'No se presentó', SIN_LUGAR: 'Sin lugar físico',
};

const tipo = (r) => (r.origen !== 'APP' ? 'Sin reserva' : r.modalidad && r.modalidad !== 'HORA' ? `Abono ${r.modalidad.toLowerCase()}` : 'App');
const horario = (r) => (r.modalidad && !['HORA', 'PRESENCIAL'].includes(r.modalidad) ? `hasta ${new Date(r.fin).toLocaleDateString('es-AR')}` : `${hora(r.inicio)}–${hora(r.fin)}`);

/** C2 · Monitor en vivo y reportes (CU-10) */
export default function MonitorPanel({ garajeId }) {
  const [ocupacion, setOcupacion] = useState(null);
  const [reservas, setReservas] = useState([]);
  const [filtro, setFiltro] = useState('TODOS');
  const [loading, setLoading] = useState(true);

  const [actualizado, setActualizado] = useState(null);
  const [cambiadas, setCambiadas] = useState(() => new Set()); // reservas que cambiaron de estado en la última consulta

  // Compara con lo que se mostraba para resaltar unos segundos las filas que cambiaron (p. ej. EN CURSO -> FINALIZADA)
  const previas = useRef([]);
  const recibir = useCallback((nuevas) => {
    const estadoAntes = new Map(previas.current.map((r) => [r.id, r.estado]));
    const distintas = previas.current.length ? nuevas.filter((r) => estadoAntes.get(r.id) !== r.estado).map((r) => r.id) : [];
    previas.current = nuevas;
    setReservas(nuevas);
    if (distintas.length) setCambiadas(new Set(distintas));
    setActualizado(new Date());
  }, []);

  const recargar = useCallback(() => Promise.all([
    garajesService.ocupacion(garajeId).then(setOcupacion),
    reservasService.list({ garaje: garajeId }).then(recibir),
  ]), [garajeId, recibir]);

  useEffect(() => {
    setLoading(true);
    setReservas([]);
    previas.current = [];
    garajesService.ocupacion(garajeId).then(setOcupacion).catch(() => {});
    reservasService.list({ garaje: garajeId }).then(recibir).finally(() => setLoading(false));
  }, [garajeId, recibir]);

  useEnVivo(recargar, 5000);

  useEffect(() => {
    if (!cambiadas.size) return undefined;
    const id = setTimeout(() => setCambiadas(new Set()), 4000);
    return () => clearTimeout(id);
  }, [cambiadas]);

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
        <Tooltip title={actualizado ? `Se actualiza solo cada 5 s · última vez ${actualizado.toLocaleTimeString('es-AR')}` : 'Se actualiza solo cada 5 s'}>
          <Chip label="En vivo" color="success" variant="outlined" sx={{ fontWeight: 800 }} />
        </Tooltip>
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
            <Leyenda color={SERIE_APP}>App y abonos</Leyenda>
            <Leyenda color={SERIE_PRESENCIAL}>Sin reserva</Leyenda>
            <Leyenda color="var(--warning)">Alerta {Math.round((ocupacion?.umbral_alerta ?? 0.9) * 100)}%</Leyenda>
          </Stack>
        )}
      >
        <GraficoOcupacion ocupacion={ocupacion} />
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
                <TableRow key={r.id} hover sx={{
                  transition: 'background-color 1.2s ease',
                  ...(cambiadas.has(r.id) ? { bgcolor: 'var(--accent-soft)' } : {}),
                }}>
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
