import { useEffect, useRef, useState } from 'react';
import { Box, Button, Skeleton, Stack, TextField, Typography } from '@mui/material';
import AddPhotoAlternateOutlined from '@mui/icons-material/AddPhotoAlternateOutlined';
import { urlDeMedia } from '../../api/client';
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
  const [foto, setFoto] = useState(null);
  const [subiendo, setSubiendo] = useState(false);
  const elegirFoto = useRef(null);

  const load = () =>
    garajesService.get(garajeId)
      .then((g) => {
        setForm({ nombre: g.nombre, cuit: g.cuit, direccion: g.direccion });
        setFoto(g.foto ?? null);
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

  const cambiarFoto = async (archivo) => {
    if (!archivo) return;
    setSubiendo(true); setMsg(null);
    try {
      setFoto((await garajesService.subirFoto(garajeId, archivo)).foto);
      setMsg({ ok: true, text: 'Foto actualizada. Los conductores ya la ven en la app.' });
    } catch (e) { setMsg({ ok: false, text: e.message }); } finally { setSubiendo(false); }
  };
  const quitarFoto = async () => {
    setSubiendo(true); setMsg(null);
    try { setFoto((await garajesService.quitarFoto(garajeId)).foto); }
    catch (e) { setMsg({ ok: false, text: e.message }); } finally { setSubiendo(false); }
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
      <Seccion titulo="Foto del estacionamiento" detalle="La entrada o el frente, para que el conductor lo reconozca al llegar. Se recorta en 16:9." sx={{ maxWidth: 720 }}>
        <Box sx={{ aspectRatio: '16 / 9', borderRadius: 2, overflow: 'hidden', bgcolor: 'var(--surface-2)', border: '1px solid var(--border)', display: 'grid', placeItems: 'center' }}>
          {foto ? (
            <Box component="img" src={urlDeMedia(foto)} alt={`Foto de ${form.nombre}`} sx={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <Stack sx={{ alignItems: 'center', color: 'text.secondary', gap: 1 }}>
              <AddPhotoAlternateOutlined sx={{ fontSize: 40 }} />
              <Typography variant="body2">Sin foto</Typography>
            </Stack>
          )}
        </Box>
        <input ref={elegirFoto} type="file" accept="image/jpeg,image/png,image/webp" hidden
          onChange={(e) => { cambiarFoto(e.target.files?.[0]); e.target.value = ''; }} />
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" onClick={() => elegirFoto.current?.click()} disabled={subiendo}>
            {subiendo ? 'Subiendo…' : foto ? 'Cambiar foto' : 'Subir foto'}
          </Button>
          {foto && <Button color="inherit" onClick={quitarFoto} disabled={subiendo} sx={{ color: 'text.secondary' }}>Quitar</Button>}
        </Stack>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>JPG, PNG o WebP de hasta 8 MB.</Typography>
      </Seccion>
    </>
  );
}
