import { useEffect, useState } from 'react';
import { Button, Skeleton, TextField } from '@mui/material';
import { garajesService } from '../../api/garajesService';
import { MONO } from '../../theme';
import { Aviso, Encabezado, Seccion } from './comun';

async function geocodificar(direccion) {
  const q = encodeURIComponent(`${direccion}, Buenos Aires, Argentina`);
  const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${q}&format=json&limit=1`, {
    headers: { 'Accept-Language': 'es' },
  });
  const data = await res.json();
  if (!data.length) throw new Error('No se encontró la dirección. Probá con más detalle, ej: "Honduras 4870, Palermo, CABA".');
  return { lat: data[0].lat, lng: data[0].lon, display: data[0].display_name };
}

/** C3 · Mi Garaje (RFW-01) */
export default function GarajePanel({ garajeId }) {
  const [form, setForm] = useState(null);
  const [geo, setGeo] = useState(null); // { lat, lng, display } — coordenadas geocodificadas
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = () =>
    garajesService.get(garajeId)
      .then((g) => {
        setForm({ nombre: g.nombre, cuit: g.cuit, direccion: g.direccion });
        if (g.lat && g.lng) setGeo({ lat: g.lat, lng: g.lng, display: null });
      })
      .catch((e) => setMsg({ ok: false, text: e.message }));

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [garajeId]);

  const set = (k, v) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (k === 'direccion') setGeo(null); // dirección cambió → coordenadas desactualizadas
  };

  const guardar = async () => {
    setSaving(true); setMsg(null);
    try {
      let coords = geo;
      if (!coords) {
        setMsg({ ok: null, text: 'Buscando coordenadas para la dirección…' });
        coords = await geocodificar(form.direccion);
        setGeo(coords);
      }
      await garajesService.updateConfiguracion(garajeId, {
        ...form,
        lat: Number(coords.lat).toFixed(6),
        lng: Number(coords.lng).toFixed(6),
      });
      setMsg({ ok: true, text: `Datos guardados. Ubicación: ${coords.display ?? `${coords.lat}, ${coords.lng}`}` });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    } finally { setSaving(false); }
  };

  if (!form) return msg ? <Aviso msg={msg} /> : <Skeleton variant="rounded" height={192} />;

  return (
    <>
      <Encabezado titulo="Mi Garaje" detalle="Datos públicos del establecimiento">
        <Button variant="contained" color="secondary" onClick={guardar} disabled={saving}>{saving ? 'Guardando…' : 'Guardar cambios'}</Button>
      </Encabezado>
      <Aviso msg={msg} />
      <Seccion titulo="Información del establecimiento" sx={{ maxWidth: 720 }}>
        <TextField label="Nombre del garaje" value={form.nombre} onChange={(e) => set('nombre', e.target.value)} placeholder="Garage Plaza Serrano" />
        <TextField label="CUIT" value={form.cuit} onChange={(e) => set('cuit', e.target.value)} placeholder="30-12345678-9" helperText="Formato: XX-XXXXXXXX-X"
          slotProps={{ htmlInput: { style: { fontFamily: MONO, letterSpacing: '0.05em' } } }} />
        <TextField label="Dirección" value={form.direccion} onChange={(e) => set('direccion', e.target.value)} placeholder="Honduras 4870, Palermo, CABA"
          helperText={geo ? `Ubicación encontrada: ${Number(geo.lat).toFixed(5)}, ${Number(geo.lng).toFixed(5)}` : 'Al guardar se buscan las coordenadas automáticamente en OpenStreetMap.'} />
      </Seccion>
    </>
  );
}
