import { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, Chip, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Typography,
} from '@mui/material';
import { garajesService } from '../../api/garajesService';
import { descargarExcel } from '../../lib/excel';
import { ars } from '../../lib/format';
import { Encabezado, Seccion } from './comun';

const iso = (d) => d.toLocaleDateString('en-CA'); // AAAA-MM-DD en hora local
const hoy = () => new Date();
const PERIODOS = [
  ['Hoy', () => [hoy(), hoy()]],
  ['Últimos 7 días', () => { const d = hoy(); d.setDate(d.getDate() - 6); return [d, hoy()]; }],
  ['Este mes', () => { const d = hoy(); return [new Date(d.getFullYear(), d.getMonth(), 1), hoy()]; }],
  ['Mes anterior', () => { const d = hoy(); return [new Date(d.getFullYear(), d.getMonth() - 1, 1), new Date(d.getFullYear(), d.getMonth(), 0)]; }],
];
const fechaHora = (t) => new Date(t).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

function Dato({ titulo, valor, detalle, color }) {
  return (
    <Card sx={{ p: 2.5 }}>
      <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 500 }}>{titulo}</Typography>
      <Typography sx={{ fontSize: 28, fontWeight: 700, mt: 0.5, color }}>{valor}</Typography>
      {detalle && <Typography variant="caption" sx={{ color: 'text.secondary' }}>{detalle}</Typography>}
    </Card>
  );
}

function Diferencia({ valor }) {
  const n = Number(valor);
  if (n === 0) return <Chip size="small" label="Justa" sx={{ bgcolor: 'var(--success-soft)', color: 'var(--success)', fontWeight: 700 }} />;
  const falta = n < 0;
  return (
    <Chip size="small" label={`${falta ? 'Faltan' : 'Sobran'} ${ars(Math.abs(n))}`}
      sx={{ bgcolor: falta ? 'var(--danger-soft)' : 'var(--warning-soft)', color: falta ? 'var(--danger)' : 'var(--warning)', fontWeight: 700 }} />
  );
}

/** Caja e informe: los cierres de caja de los playeros y lo cobrado por cada medio, con Excel y PDF. */
export default function CajaPanel({ garajeId }) {
  const [rango, setRango] = useState(() => PERIODOS[0][1]().map(iso));
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [bajando, setBajando] = useState(false);
  const params = { desde: rango[0], hasta: rango[1] };

  useEffect(() => {
    setDatos(null); setError(null);
    garajesService.informe(garajeId, { desde: rango[0], hasta: rango[1] }).then(setDatos).catch((e) => setError(e.message));
  }, [garajeId, rango]);

  const nombreArchivo = `drivly-informe-${rango[0]}${rango[0] === rango[1] ? '' : `-al-${rango[1]}`}`;
  const excel = () => {
    const filas = [
      ...datos.ingresos.map((f) => ({ seccion: 'Ingresos', concepto: f.concepto, detalle: f.medio, cantidad: f.cantidad, importe: f.total })),
      { seccion: 'Ingresos', concepto: 'Total cobrado', detalle: '', cantidad: '', importe: datos.total_ingresos },
      { seccion: 'Ingresos', concepto: 'Comisión de Drivly', detalle: 'Retenida por Mercado Pago', cantidad: '', importe: -Number(datos.comision_drivly) },
      { seccion: 'Ingresos', concepto: 'Neto para el garaje', detalle: '', cantidad: '', importe: datos.neto_garaje },
      { seccion: 'Actividad', concepto: 'Excesos condonados', detalle: '', cantidad: datos.excesos_generados, importe: datos.condonado },
      { seccion: 'Actividad', concepto: 'Reembolsos', detalle: '', cantidad: datos.reembolsos.cantidad, importe: datos.reembolsos.total },
      { seccion: 'Actividad', concepto: 'Deuda pendiente al día de hoy', detalle: '', cantidad: '', importe: datos.deuda_pendiente },
      ...datos.cierres.map((c) => ({
        seccion: 'Cierre de caja', concepto: `${fechaHora(c.fecha)} · ${c.cerrado_por}`,
        detalle: `Esperado ${ars(c.efectivo_esperado)} · contado ${ars(c.efectivo_contado)}${c.observaciones ? ` · ${c.observaciones}` : ''}`,
        cantidad: '', importe: c.diferencia,
      })),
    ];
    descargarExcel(`${nombreArchivo}.xlsx`, 'Informe', filas, [
      { label: 'Sección', value: (f) => f.seccion, ancho: 16 },
      { label: 'Concepto', value: (f) => f.concepto, ancho: 34 },
      { label: 'Medio / detalle', value: (f) => f.detalle, ancho: 44 },
      { label: 'Cantidad', value: (f) => f.cantidad, ancho: 10 },
      { label: 'Importe', value: (f) => f.importe, tipo: 'importe', ancho: 16 },
    ]);
  };
  const pdf = async () => {
    setBajando(true);
    try { await garajesService.informePdf(garajeId, params); } catch (e) { setError(e.message); } finally { setBajando(false); }
  };

  return (
    <>
      <Encabezado titulo="Caja e informe" detalle="Lo cobrado por cada medio y los cierres de caja que hacen tus playeros desde la app.">
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" onClick={excel} disabled={!datos}>Exportar Excel</Button>
          <Button variant="contained" onClick={pdf} disabled={!datos || bajando}>{bajando ? 'Generando…' : 'Descargar PDF'}</Button>
        </Stack>
      </Encabezado>

      <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
        {PERIODOS.map(([texto, calcular]) => {
          const [d, h] = calcular().map(iso);
          const activo = d === rango[0] && h === rango[1];
          return <Chip key={texto} label={texto} clickable onClick={() => setRango([d, h])} color={activo ? 'primary' : 'default'}
            variant={activo ? 'filled' : 'outlined'} sx={{ fontWeight: 600 }} />;
        })}
        <TextField type="date" size="small" label="Desde" value={rango[0]} onChange={(e) => e.target.value && setRango([e.target.value, rango[1]])}
          slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: rango[1] } }} />
        <TextField type="date" size="small" label="Hasta" value={rango[1]} onChange={(e) => e.target.value && setRango([rango[0], e.target.value])}
          slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: rango[0], max: iso(hoy()) } }} />
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {!datos && !error && <Skeleton variant="rounded" height={320} />}
      {datos && (
        <>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' } }}>
            <Dato titulo="Total cobrado" valor={ars(datos.total_ingresos)} detalle={`${datos.reservas_por_app} por la app · ${datos.clientes_sin_reserva} sin reserva`} />
            <Dato titulo="Neto para el garaje" valor={ars(datos.neto_garaje)} detalle={`Comisión de Drivly ${ars(datos.comision_drivly)}`} />
            <Dato titulo="Efectivo cobrado" valor={ars(datos.efectivo_cobrado)} detalle="Debería estar en la caja" />
            <Dato titulo="Diferencia de los cierres" valor={ars(datos.diferencia_cierres)}
              color={Number(datos.diferencia_cierres) < 0 ? 'var(--danger)' : undefined}
              detalle={`${datos.cierres.length} ${datos.cierres.length === 1 ? 'cierre' : 'cierres'} en el período`} />
          </Box>

          {datos.presenciales_sin_medio > 0 && (
            <Alert severity="warning">{datos.presenciales_sin_medio} cobro(s) a clientes sin reserva no tienen medio marcado: se cuentan como efectivo.</Alert>
          )}

          <Seccion titulo="Ingresos por medio">
            <TableContainer>
              <Table size="small">
                <TableHead><TableRow><TableCell>Concepto</TableCell><TableCell>Medio</TableCell><TableCell align="right">Cantidad</TableCell><TableCell align="right">Total</TableCell></TableRow></TableHead>
                <TableBody>
                  {datos.ingresos.map((f) => (
                    <TableRow key={`${f.concepto}-${f.medio}`}>
                      <TableCell>{f.concepto}</TableCell><TableCell sx={{ color: 'text.secondary' }}>{f.medio}</TableCell>
                      <TableCell align="right">{f.cantidad}</TableCell><TableCell align="right" sx={{ fontWeight: 600 }}>{ars(f.total)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell colSpan={3} sx={{ fontWeight: 700 }}>Total</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 800 }}>{ars(datos.total_ingresos)}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
            <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap', columnGap: 3, rowGap: 0.5 }}>
              {[['Excesos generados', datos.excesos_generados], ['Excesos condonados', ars(datos.condonado)], ['Cancelaciones', datos.cancelaciones],
                [`Reembolsos (${datos.reembolsos.cantidad})`, ars(datos.reembolsos.total)], ['Deuda pendiente hoy', ars(datos.deuda_pendiente)]]
                .map(([t, v]) => <Typography key={t} variant="body2" sx={{ color: 'text.secondary' }}>{t}: <b style={{ color: 'var(--text-primary)' }}>{v}</b></Typography>)}
            </Stack>
          </Seccion>

          <Seccion titulo="Cierres de caja" detalle="Los hace el playero desde la app al terminar el día. La diferencia es lo contado menos lo esperado.">
            {datos.cierres.length === 0 ? (
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>No hubo cierres de caja en el período.</Typography>
            ) : (
              <TableContainer>
                <Table size="small" sx={{ minWidth: 640 }}>
                  <TableHead><TableRow><TableCell>Fecha</TableCell><TableCell>Cerró</TableCell><TableCell align="right">Esperado</TableCell><TableCell align="right">Contado</TableCell><TableCell>Diferencia</TableCell><TableCell>Observaciones</TableCell></TableRow></TableHead>
                  <TableBody>
                    {datos.cierres.map((c) => (
                      <TableRow key={c.fecha}>
                        <TableCell sx={{ whiteSpace: 'nowrap' }}>{fechaHora(c.fecha)}</TableCell>
                        <TableCell>{c.cerrado_por}</TableCell>
                        <TableCell align="right">{ars(c.efectivo_esperado)}</TableCell>
                        <TableCell align="right">{ars(c.efectivo_contado)}</TableCell>
                        <TableCell><Diferencia valor={c.diferencia} /></TableCell>
                        <TableCell sx={{ color: 'text.secondary' }}>{c.observaciones || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Seccion>
        </>
      )}
    </>
  );
}
