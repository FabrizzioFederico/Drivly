import { useEffect, useState } from 'react';
import {
  Box, Button, Card, CardContent, Divider, FormHelperText, IconButton, InputAdornment, InputBase, LinearProgress, MenuItem,
  Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography, useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Add from '@mui/icons-material/Add';
import InfoOutlined from '@mui/icons-material/InfoOutlined';
import Remove from '@mui/icons-material/Remove';
import { garajesService } from '../../api/garajesService';
import { ars, CATEGORIA_LABEL, miles } from '../../lib/format';
import { Aviso, Encabezado, Leyenda, Seccion } from './comun';

const CATEGORIAS = ['AUTO', 'MOTO', 'CAMIONETA'];
const ABONOS = ['SEMANAL', 'MENSUAL', 'ANUAL'];
const ABONO_LABEL = { SEMANAL: 'Semanal', MENSUAL: 'Mensual', ANUAL: 'Anual' };
const MINIMOS = [15, 30, 60, 120]; // minutos mínimos cobrados = minimo_fracciones × 15
const SALIDAS = [60, 90, 120, 180, 240];
const minLabel = (m) => (m >= 60 ? `${m / 60} h` : `${m} min`);
const iguales = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** Pasa de las filas del backend a la forma de los formularios. */
function desdeFilas(filas) {
  const hora = CATEGORIAS.map((categoria) => {
    const t = filas.find((f) => f.categoria === categoria && f.modalidad === 'HORA');
    // Number: el backend manda "340.00" y en los campos alcanza con 340
    return { categoria, precio_fraccion: Number(t?.precio_fraccion ?? 0), minimo_min: (t?.minimo_fracciones ?? 1) * (t?.fraccion_min ?? 15) };
  });
  const abonos = Object.fromEntries(CATEGORIAS.map((c) => [c, Object.fromEntries(ABONOS.map((m) => {
    const t = filas.find((f) => f.categoria === c && f.modalidad === m);
    return [m, t ? Number(t.precio_periodo) : ''];
  }))]));
  return { hora, abonos };
}

/** Y de vuelta: una fila por categoría y modalidad. Un abono sin precio deja de ofrecerse. */
function aFilas({ hora, abonos }) {
  const filas = hora
    .filter((h) => Number(h.precio_fraccion) > 0)
    .map((h) => ({ categoria: h.categoria, modalidad: 'HORA', precio_fraccion: h.precio_fraccion, fraccion_min: 15, minimo_fracciones: h.minimo_min / 15, precio_periodo: null }));
  CATEGORIAS.forEach((c) => ABONOS.forEach((m) => {
    const precio = Number(abonos[c][m]);
    if (precio > 0) filas.push({ categoria: c, modalidad: m, precio_fraccion: null, fraccion_min: null, minimo_fracciones: null, precio_periodo: precio });
  }));
  return filas;
}

const Punto = () => <Box component="span" role="img" aria-label="Modificado sin guardar" sx={{ display: 'inline-block', flexShrink: 0, width: 6, height: 6, borderRadius: '50%', bgcolor: 'var(--warning)' }} />;

function Etiqueta({ children, modificado }) {
  return (
    <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', mb: 0.75 }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>{children}</Typography>
      {modificado && <Punto />}
    </Stack>
  );
}

function Variacion({ valor }) {
  const sube = valor > 0;
  const baja = valor < 0;
  const [fondo, color] = sube ? ['var(--success-soft)', 'var(--success)'] : baja ? ['var(--danger-soft)', 'var(--danger)'] : ['var(--surface-2)', 'var(--text-muted)'];
  return (
    <Box component="span" sx={{ px: 1, py: 0.25, borderRadius: 1, bgcolor: fondo, color, fontSize: 13, fontWeight: 600 }}>
      {sube ? `↑ +${valor}` : baja ? `↓ ${valor}` : valor} vs. semana anterior
    </Box>
  );
}

function Kpi({ titulo, children }) {
  return (
    <Card>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1, p: 3, '&:last-child': { pb: 3 } }}>
        <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 500 }}>{titulo}</Typography>
        {children}
      </CardContent>
    </Card>
  );
}

const Numero = ({ children }) => <Typography component="span" sx={{ fontSize: 34, fontWeight: 700, lineHeight: 1.2 }}>{children}</Typography>;

function Kpis({ m }) {
  const grilla = { display: 'grid', gap: 3, gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'repeat(3, minmax(0, 1fr))' } };
  if (m === null) return <Box sx={grilla}>{[0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={120} />)}</Box>;
  if (m.ocupacion_pico === undefined) return null;
  return (
    <Box sx={grilla}>
      <Kpi titulo="Ocupación pico del día">
        <Stack direction="row" spacing={1.25} useFlexGap sx={{ alignItems: 'baseline', flexWrap: 'wrap' }}>
          <Numero>{Math.round(m.ocupacion_pico * 100)}%</Numero>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>{m.ocupacion_pico_lugares} lugares · {m.ocupacion_pico_hora}</Typography>
        </Stack>
        <LinearProgress variant="determinate" value={m.ocupacion_pico * 100} aria-label="Ocupación pico del día" sx={{ height: 6, borderRadius: 3, bgcolor: 'var(--surface-2)', '& .MuiLinearProgress-bar': { bgcolor: 'var(--accent)', borderRadius: 3 } }} />
      </Kpi>
      <Kpi titulo="Reservas confirmadas hoy">
        <Stack direction="row" spacing={1.25} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <Numero>{m.reservas_confirmadas}</Numero>
          <Variacion valor={m.reservas_variacion} />
        </Stack>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          <Box component="span" sx={m.en_hold > 0 ? { color: 'var(--warning)', fontWeight: 600 } : undefined}>{m.en_hold} en HOLD</Box> · {m.canceladas} canceladas
        </Typography>
      </Kpi>
      <Kpi titulo="Recaudación total">
        <Numero>{ars(m.recaudacion_total)}</Numero>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>App {ars(m.recaudacion_app)} · Presencial {ars(m.recaudacion_presencial)} · Excedentes {ars(m.recaudacion_excedentes)}</Typography>
        {(m.deuda_pendiente > 0 || m.deuda_incobrable > 0) && (
          <Typography variant="body2" sx={{ color: 'var(--danger)', fontWeight: 600 }}>Por cobrar {ars(m.deuda_pendiente)} · Incobrable {ars(m.deuda_incobrable)}</Typography>
        )}
      </Kpi>
    </Box>
  );
}

function Stepper({ etiqueta, value, onChange, min = 0, max }) {
  const boton = { borderRadius: 1, color: 'text.secondary', '&:hover': { color: 'var(--accent)', bgcolor: 'transparent' } };
  return (
    <Box sx={{
      display: 'flex', alignItems: 'center', flexShrink: 0, height: 40, width: 136, px: 0.5, borderRadius: 1, bgcolor: 'var(--surface-2)', border: '1px solid var(--border)',
      '&:hover': { borderColor: 'var(--border-hover)' }, '&:focus-within': { borderColor: 'var(--accent)', boxShadow: '0 0 0 3px rgba(0,194,168,0.25)' },
    }}>
      <IconButton size="small" onClick={() => onChange(Math.max(min, value - 1))} aria-label={`Restar a ${etiqueta}`} sx={boton}><Remove fontSize="small" /></IconButton>
      <InputBase value={value} onChange={(e) => { const n = parseInt(e.target.value, 10); if (!Number.isNaN(n)) onChange(Math.min(max, Math.max(min, n))); }}
        sx={{ flex: 1 }} slotProps={{ input: { inputMode: 'numeric', 'aria-label': etiqueta, style: { textAlign: 'center', fontWeight: 600 } } }} />
      <IconButton size="small" onClick={() => onChange(Math.min(max, value + 1))} aria-label={`Sumar a ${etiqueta}`} sx={boton}><Add fontSize="small" /></IconButton>
    </Box>
  );
}

function Campo({ titulo, detalle, modificado, error, children }) {
  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Box>
          <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{titulo}</Typography>
            {modificado && <Punto />}
          </Stack>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{detalle}</Typography>
        </Box>
        {children}
      </Stack>
      {error && <FormHelperText error>{error}</FormHelperText>}
    </Box>
  );
}

/** Muestra el monto con miles ($ 45.000) y, mientras se edita, el número tal cual se escribe. */
function CampoMonto({ etiqueta, value, onChange, placeholder }) {
  const [texto, setTexto] = useState(null); // null = no se está editando
  const crudo = value === '' ? '' : String(value).replace('.', ',');

  const cambiar = (e) => {
    const t = e.target.value.replace(/\./g, '');
    if (!/^\d*(,\d{0,2})?$/.test(t)) return;
    setTexto(t);
    onChange(t === '' ? '' : Number(t.replace(',', '.')));
  };

  // Al pasar al número crudo cambia el valor y se pierde la selección: sin esto lo escrito se suma al monto anterior
  const enfocar = (e) => {
    const campo = e.target;
    setTexto(crudo);
    requestAnimationFrame(() => campo.select());
  };

  return (
    <TextField
      size="small" fullWidth placeholder={placeholder} title={placeholder ? 'Vacío: no se ofrece' : undefined}
      value={texto ?? (value === '' ? '' : miles(value))} onChange={cambiar} onFocus={enfocar} onBlur={() => setTexto(null)}
      slotProps={{
        htmlInput: { inputMode: 'decimal', 'aria-label': etiqueta },
        input: { startAdornment: <InputAdornment position="start">$</InputAdornment> },
      }}
    />
  );
}

function SelectMinimo({ etiqueta, value, onChange }) {
  return (
    <TextField select size="small" fullWidth value={value} onChange={(e) => onChange(Number(e.target.value))} slotProps={{ htmlInput: { 'aria-label': etiqueta } }}>
      {MINIMOS.map((m) => <MenuItem key={m} value={m}>{minLabel(m)}</MenuItem>)}
    </TextField>
  );
}

/** En el celular las tablas pasan a una tarjeta por categoría. */
function TarjetaCategoria({ titulo, modificado, children }) {
  return (
    <Box sx={{ p: 2, border: '1px solid var(--border)', borderRadius: 1.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>{titulo}</Typography>
        {modificado && <Punto />}
      </Stack>
      {children}
    </Box>
  );
}

function FilaCategoria({ titulo, modificado, children }) {
  return (
    <TableRow>
      <TableCell sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
        <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}><span>{titulo}</span>{modificado && <Punto />}</Stack>
      </TableCell>
      {children}
    </TableRow>
  );
}

function TablaHora({ tarifas, base, setHora, movil }) {
  const cambio = (i, k) => tarifas.hora[i][k] !== base.hora[i][k];
  if (movil) {
    return tarifas.hora.map((t, i) => (
      <TarjetaCategoria key={t.categoria} titulo={CATEGORIA_LABEL[t.categoria]}>
        <Box>
          <Etiqueta modificado={cambio(i, 'precio_fraccion')}>Precio por fracción</Etiqueta>
          <CampoMonto etiqueta={`Precio por fracción ${CATEGORIA_LABEL[t.categoria]}`} value={t.precio_fraccion} onChange={(v) => setHora(i, 'precio_fraccion', v === '' ? 0 : v)} />
        </Box>
        <Box>
          <Etiqueta modificado={cambio(i, 'minimo_min')}>Mínimo cobrado</Etiqueta>
          <SelectMinimo etiqueta={`Mínimo cobrado ${CATEGORIA_LABEL[t.categoria]}`} value={t.minimo_min} onChange={(v) => setHora(i, 'minimo_min', v)} />
        </Box>
      </TarjetaCategoria>
    ));
  }
  return (
    <TableContainer>
      <Table size="small">
        <TableHead><TableRow><TableCell>Categoría</TableCell><TableCell>Precio por fracción</TableCell><TableCell>Mínimo cobrado</TableCell></TableRow></TableHead>
        <TableBody>
          {tarifas.hora.map((t, i) => (
            <FilaCategoria key={t.categoria} titulo={CATEGORIA_LABEL[t.categoria]} modificado={cambio(i, 'precio_fraccion') || cambio(i, 'minimo_min')}>
              <TableCell sx={{ py: 1 }}><CampoMonto etiqueta={`Precio por fracción ${CATEGORIA_LABEL[t.categoria]}`} value={t.precio_fraccion} onChange={(v) => setHora(i, 'precio_fraccion', v === '' ? 0 : v)} /></TableCell>
              <TableCell sx={{ py: 1 }}><SelectMinimo etiqueta={`Mínimo cobrado ${CATEGORIA_LABEL[t.categoria]}`} value={t.minimo_min} onChange={(v) => setHora(i, 'minimo_min', v)} /></TableCell>
            </FilaCategoria>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function TablaAbonos({ tarifas, base, setAbono, movil }) {
  const cambio = (c, m) => tarifas.abonos[c][m] !== base.abonos[c][m];
  const campo = (c, m) => <CampoMonto etiqueta={`Abono ${m.toLowerCase()} ${CATEGORIA_LABEL[c]}`} placeholder="No ofrecido" value={tarifas.abonos[c][m]} onChange={(v) => setAbono(c, m, v)} />;
  if (movil) {
    return CATEGORIAS.map((c) => (
      <TarjetaCategoria key={c} titulo={CATEGORIA_LABEL[c]}>
        {ABONOS.map((m) => <Box key={m}><Etiqueta modificado={cambio(c, m)}>{ABONO_LABEL[m]}</Etiqueta>{campo(c, m)}</Box>)}
      </TarjetaCategoria>
    ));
  }
  return (
    <TableContainer>
      <Table size="small">
        <TableHead><TableRow><TableCell>Categoría</TableCell>{ABONOS.map((m) => <TableCell key={m}>{ABONO_LABEL[m]}</TableCell>)}</TableRow></TableHead>
        <TableBody>
          {CATEGORIAS.map((c) => (
            <FilaCategoria key={c} titulo={CATEGORIA_LABEL[c]} modificado={ABONOS.some((m) => cambio(c, m))}>
              {ABONOS.map((m) => <TableCell key={m} sx={{ py: 1, px: 0.5 }}>{campo(c, m)}</TableCell>)}
            </FilaCategoria>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

const FilaPrevia = ({ texto, valor, color }) => (
  <Stack direction="row" spacing={1.5} sx={{ justifyContent: 'space-between' }}>
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>{texto}</Typography>
    <Typography variant="body2" sx={{ fontWeight: 600, color, whiteSpace: 'nowrap' }}>{valor}</Typography>
  </Stack>
);

function Acciones({ hayCambios, saving, invalido, onDescartar, onGuardar }) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap' }} useFlexGap>
      {hayCambios && (
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }} role="status">
          <Punto />
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>Cambios sin guardar</Typography>
        </Stack>
      )}
      <Button variant="outlined" onClick={onDescartar} disabled={!hayCambios || saving}>Descartar</Button>
      <Button variant="contained" onClick={onGuardar} disabled={!hayCambios || saving || invalido}>{saving ? 'Guardando…' : 'Guardar cambios'}</Button>
    </Stack>
  );
}

/** C1 · Capacidad y Tarifas (CU-06) */
export default function TarifasPanel({ garajeId }) {
  const movil = useMediaQuery(useTheme().breakpoints.down('sm'), { noSsr: true });
  const [garaje, setGaraje] = useState(null);
  const [base, setBase] = useState(null); // lo último guardado: contra esto se detectan los cambios
  const [config, setConfig] = useState(null);
  const [tarifas, setTarifas] = useState(null);
  const [metricas, setMetricas] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [errores, setErrores] = useState({});

  const load = () => Promise.all([garajesService.get(garajeId), garajesService.getTarifas(garajeId)])
    .then(([g, t]) => {
      const c = { capacidad: g.capacidad, cupo_abonos: g.cupo_abonos, salida_estimada_default_min: g.salida_estimada_default_min, tolerancia_min: g.tolerancia_min, recargo_overstay: Number(g.recargo_overstay) };
      const f = desdeFilas(t);
      setGaraje(g); setConfig(c); setTarifas(f); setBase({ config: c, tarifas: f }); setMsg(null); setErrores({});
      // Un fallo de las métricas no impide editar capacidad y tarifas
      garajesService.metricas(garajeId).then(setMetricas).catch(() => setMetricas({}));
    })
    .catch((e) => setMsg({ ok: false, text: e.message }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [garajeId]);

  const set = (k, v) => setConfig((c) => ({ ...c, [k]: v, ...(k === 'capacidad' && c.cupo_abonos > v ? { cupo_abonos: v } : {}) }));
  const setHora = (i, k, v) => setTarifas((t) => ({ ...t, hora: t.hora.map((row, j) => (j === i ? { ...row, [k]: v } : row)) }));
  const setAbono = (c, m, v) => setTarifas((t) => ({ ...t, abonos: { ...t.abonos, [c]: { ...t.abonos[c], [m]: v } } }));

  const guardar = async () => {
    setSaving(true); setMsg(null); setErrores({});
    try {
      await Promise.all([garajesService.updateConfiguracion(garajeId, config), garajesService.updateTarifas(garajeId, aFilas(tarifas))]);
      setBase({ config, tarifas });
      setMsg({ ok: true, text: 'Cambios guardados. Aplican a reservas nuevas.' });
    } catch (e) { setErrores(e.fields ?? {}); setMsg({ ok: false, text: e.message }); } finally { setSaving(false); }
  };

  if (!config || !tarifas) return msg ? <Aviso msg={msg} /> : <Skeleton variant="rounded" height={256} />;

  const auto = tarifas.hora.find((t) => t.categoria === 'AUTO');
  const pctAbonos = (config.cupo_abonos / (config.capacidad || 1)) * 100;
  const recargoPct = Math.round(config.recargo_overstay * 100);
  const cambio = (k) => config[k] !== base.config[k];
  const error = (k) => errores[k]?.[0];
  const hayCambios = !iguales({ config, tarifas }, base);
  const acciones = <Acciones hayCambios={hayCambios} saving={saving} invalido={config.cupo_abonos > config.capacidad} onDescartar={load} onGuardar={guardar} />;

  return (
    <>
      <Encabezado titulo="Capacidad y Tarifas" detalle={garaje?.direccion}>{!movil && acciones}</Encabezado>
      <Aviso msg={msg} />
      <Kpis m={metricas} />

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: 'minmax(0, 1fr)', lg: 'minmax(0, 1fr) minmax(0, 1.55fr)' }, alignItems: 'start' }}>
        <Seccion titulo="Capacidad" detalle="Una sola capacidad para todos: conductores de la app, abonados y clientes sin reserva.">
          <Campo titulo="Lugares en Drivly" detalle="Pueden ser menos que los físicos" modificado={cambio('capacidad')} error={error('capacidad')}>
            <Stepper etiqueta="Lugares en Drivly" value={config.capacidad} min={1} max={2000} onChange={(v) => set('capacidad', v)} />
          </Campo>
          <Campo titulo="Máximo para abonos" detalle="Semanales, mensuales y anuales, sin lugar fijo" modificado={cambio('cupo_abonos')} error={error('cupo_abonos')}>
            <Stepper etiqueta="Máximo para abonos" value={config.cupo_abonos} max={config.capacidad} onChange={(v) => set('cupo_abonos', v)} />
          </Campo>
          <Stack spacing={1}>
            <Stack direction="row" spacing={0.25} sx={{ height: 8 }} role="img" aria-label={`Hasta ${config.cupo_abonos} de ${config.capacidad} lugares para abonos`}>
              <Box sx={{ width: `${pctAbonos}%`, bgcolor: 'var(--accent-strong)', borderRadius: '4px 0 0 4px' }} />
              <Box sx={{ flex: 1, bgcolor: 'var(--accent)', borderRadius: '0 4px 4px 0' }} />
            </Stack>
            <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap', columnGap: 2, rowGap: 0.5 }}>
              <Leyenda color="var(--accent-strong)">Hasta {config.cupo_abonos} para abonos</Leyenda>
              <Leyenda color="var(--accent)">El resto rota entre app y clientes sin reserva</Leyenda>
            </Stack>
          </Stack>
          <Campo titulo="Salida estimada sin reserva" detalle="Lo que el semáforo asume si el playero no indica otra" modificado={cambio('salida_estimada_default_min')}>
            <TextField select size="small" value={config.salida_estimada_default_min} onChange={(e) => set('salida_estimada_default_min', Number(e.target.value))}
              sx={{ width: 112, flexShrink: 0 }} slotProps={{ htmlInput: { 'aria-label': 'Salida estimada sin reserva' } }}>
              {SALIDAS.map((m) => <MenuItem key={m} value={m}>{minLabel(m)}</MenuItem>)}
            </TextField>
          </Campo>

          <Divider />
          <Typography variant="h3">Exceso de permanencia</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <Box>
              <Etiqueta modificado={cambio('tolerancia_min')}>Tolerancia</Etiqueta>
              <TextField type="number" size="small" fullWidth value={config.tolerancia_min} onChange={(e) => set('tolerancia_min', Number(e.target.value))} error={Boolean(error('tolerancia_min'))} helperText={error('tolerancia_min')}
                slotProps={{ htmlInput: { min: 0, 'aria-label': 'Tolerancia' }, input: { endAdornment: <InputAdornment position="end">min</InputAdornment> } }} />
            </Box>
            <Box>
              <Etiqueta modificado={cambio('recargo_overstay')}>Recargo</Etiqueta>
              <TextField type="number" size="small" fullWidth value={recargoPct} onChange={(e) => set('recargo_overstay', Number(e.target.value) / 100)} error={Boolean(error('recargo_overstay'))} helperText={error('recargo_overstay')}
                slotProps={{ htmlInput: { min: 0, step: 5, 'aria-label': 'Recargo' }, input: { endAdornment: <InputAdornment position="end">%</InputAdornment> } }} />
            </Box>
          </Box>
          <Stack direction="row" spacing={1.5} sx={{ p: 1.5, borderRadius: 1, bgcolor: 'var(--accent-soft)', borderLeft: '3px solid var(--accent)' }}>
            <InfoOutlined fontSize="small" sx={{ color: 'var(--accent)' }} />
            <Typography variant="body2">Los cambios aplican a reservas nuevas. Las reservas y abonos vigentes se respetan.</Typography>
          </Stack>
        </Seccion>

        <Stack spacing={3} sx={{ minWidth: 0 }}>
          <Seccion titulo="Tarifas por hora" accion={<Typography variant="caption" sx={{ color: 'text.secondary' }}>Se cobra por fracción de 15 min</Typography>}>
            <TablaHora tarifas={tarifas} base={base.tarifas} setHora={setHora} movil={movil} />
          </Seccion>

          <Seccion titulo="Abonos" detalle="Precio por período completo. Dejalo vacío si no ofrecés esa opción.">
            <TablaAbonos tarifas={tarifas} base={base.tarifas} setAbono={setAbono} movil={movil} />
          </Seccion>

          {auto && (
            <Seccion titulo="Vista previa para el conductor">
              <Stack spacing={1}>
                <FilaPrevia texto={`Auto · 3 h = 12 × ${ars(auto.precio_fraccion)}`} valor={ars(12 * auto.precio_fraccion)} />
                <FilaPrevia texto={`Overstay 30 min = 2 × ${ars(auto.precio_fraccion)} + ${recargoPct} %`} valor={ars(Math.round(2 * auto.precio_fraccion * (1 + config.recargo_overstay)))} color="var(--danger)" />
                {tarifas.abonos.AUTO.MENSUAL !== '' && <FilaPrevia texto="Auto · abono mensual" valor={ars(tarifas.abonos.AUTO.MENSUAL)} />}
              </Stack>
            </Seccion>
          )}
        </Stack>
      </Box>

      {movil && (
        <>
          <Box sx={{ height: 72 }} />{/* para que la barra fija no tape el final de la página */}
          <Box sx={{ position: 'fixed', zIndex: 'appBar', left: 0, right: 0, bottom: 0, p: 1.5, bgcolor: 'var(--surface-1)', borderTop: '1px solid var(--border)' }}>{acciones}</Box>
        </>
      )}
    </>
  );
}
