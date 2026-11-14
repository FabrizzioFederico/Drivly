import { useEffect, useState } from 'react';
import { Alert, Box, Button, Card, Divider, Rating, Skeleton, Stack, TextField, Typography } from '@mui/material';
import { garajesService } from '../../api/garajesService';
import { Encabezado, Seccion } from './comun';

const fecha = (iso) => new Date(iso).toLocaleDateString('es-AR', { day: 'numeric', month: 'short', year: 'numeric' });
const promedioTexto = (n) => (n == null ? '—' : n.toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }));

/** Cuántas reseñas hay de cada cantidad de estrellas: barras de un solo color, con el número al lado. */
function Distribucion({ porEstrellas, total }) {
  return (
    <Stack spacing={0.75} sx={{ flex: 1, minWidth: 220 }} role="list" aria-label="Reseñas por cantidad de estrellas">
      {['5', '4', '3', '2', '1'].map((n) => {
        const cantidad = porEstrellas?.[n] ?? 0;
        const ancho = total ? (cantidad / total) * 100 : 0;
        return (
          <Stack key={n} direction="row" spacing={1.5} sx={{ alignItems: 'center' }} role="listitem"
            aria-label={`${n} estrellas: ${cantidad}`}>
            <Typography variant="body2" sx={{ width: 28, color: 'text.secondary' }}>{n} ★</Typography>
            <Box sx={{ flex: 1, height: 8, borderRadius: 4, bgcolor: 'var(--surface-2)', overflow: 'hidden' }}>
              <Box sx={{ width: `${ancho}%`, height: '100%', borderRadius: 4, bgcolor: 'var(--accent)' }} />
            </Box>
            <Typography variant="body2" sx={{ width: 24, textAlign: 'right' }}>{cantidad}</Typography>
          </Stack>
        );
      })}
    </Stack>
  );
}

function Opinion({ resena, garajeId, alResponder }) {
  const [abierta, setAbierta] = useState(false);
  const [texto, setTexto] = useState(resena.respuesta);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  const guardar = async (valor) => {
    setGuardando(true); setError(null);
    try {
      alResponder(await garajesService.responderResena(garajeId, resena.id, valor));
      setAbierta(false);
    } catch (e) { setError(e.message); } finally { setGuardando(false); }
  };

  return (
    <Stack spacing={1} sx={{ py: 2 }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
        <Rating value={resena.estrellas} readOnly size="small" />
        <Typography variant="body2" sx={{ fontWeight: 600 }}>{resena.autor}</Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>{fecha(resena.creada_en)}</Typography>
      </Stack>
      {resena.comentario
        ? <Typography variant="body2">{resena.comentario}</Typography>
        : <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>Sin comentario</Typography>}

      {resena.respuesta && !abierta && (
        <Box sx={{ pl: 2, borderLeft: '3px solid var(--accent)' }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>Tu respuesta · {fecha(resena.respondida_en)}</Typography>
          <Typography variant="body2">{resena.respuesta}</Typography>
        </Box>
      )}

      {abierta ? (
        <Stack spacing={1}>
          <TextField multiline minRows={2} size="small" label="Tu respuesta (la ven los conductores)" value={texto}
            onChange={(e) => setTexto(e.target.value.slice(0, 500))} helperText={`${texto.length}/500`} autoFocus />
          {error && <Alert severity="error">{error}</Alert>}
          <Stack direction="row" spacing={1}>
            <Button variant="contained" size="small" onClick={() => guardar(texto)} disabled={guardando || !texto.trim()}>
              {guardando ? 'Guardando…' : 'Publicar respuesta'}
            </Button>
            <Button size="small" color="inherit" onClick={() => { setAbierta(false); setTexto(resena.respuesta); }}>Cancelar</Button>
          </Stack>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1}>
          <Button size="small" onClick={() => setAbierta(true)}>{resena.respuesta ? 'Editar respuesta' : 'Responder'}</Button>
          {resena.respuesta && (
            <Button size="small" color="inherit" sx={{ color: 'text.secondary' }} onClick={() => guardar('')} disabled={guardando}>Borrar respuesta</Button>
          )}
        </Stack>
      )}
    </Stack>
  );
}

/** Opiniones: lo que califican los conductores después de estacionar, con la respuesta del garaje. */
export default function OpinionesPanel({ garajeId }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [pagina, setPagina] = useState(1);
  const [cargandoMas, setCargandoMas] = useState(false);

  useEffect(() => {
    setDatos(null); setError(null); setPagina(1);
    garajesService.resenas(garajeId).then(setDatos).catch((e) => setError(e.message));
  }, [garajeId]);

  const masOpiniones = async () => {
    setCargandoMas(true);
    try {
      const siguiente = await garajesService.resenas(garajeId, pagina + 1);
      setDatos((d) => ({ ...siguiente, results: [...d.results, ...siguiente.results] }));
      setPagina((p) => p + 1);
    } catch (e) { setError(e.message); } finally { setCargandoMas(false); }
  };
  const actualizar = (resena) => setDatos((d) => ({ ...d, results: d.results.map((r) => (r.id === resena.id ? resena : r)) }));

  const resumen = datos?.resumen;
  return (
    <>
      <Encabezado titulo="Opiniones" detalle="Las calificaciones que dejan los conductores al terminar su estadía. Se ven en la app antes de reservar." />
      {error && <Alert severity="error">{error}</Alert>}
      {!datos && !error && <Skeleton variant="rounded" height={260} />}
      {datos && (
        <>
          <Card sx={{ p: 3 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={4} sx={{ alignItems: { sm: 'center' } }}>
              <Stack spacing={0.5} sx={{ alignItems: { xs: 'flex-start', sm: 'center' }, minWidth: 160 }}>
                <Typography sx={{ fontSize: 48, fontWeight: 800, lineHeight: 1 }}>{promedioTexto(resumen.estrellas)}</Typography>
                <Rating value={resumen.estrellas ?? 0} precision={0.1} readOnly aria-label={`Promedio ${promedioTexto(resumen.estrellas)} de 5`} />
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  {resumen.cantidad === 1 ? '1 opinión' : `${resumen.cantidad} opiniones`}
                </Typography>
              </Stack>
              <Distribucion porEstrellas={resumen.por_estrellas} total={resumen.cantidad} />
            </Stack>
          </Card>

          <Seccion titulo="Comentarios" detalle="Respondé con amabilidad: tu respuesta aparece debajo del comentario en la app.">
            {datos.results.length === 0 ? (
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Todavía no hay opiniones. Los conductores pueden calificar desde la app cuando termina su estadía.
              </Typography>
            ) : (
              <Box>
                {datos.results.map((r, i) => (
                  <Box key={r.id}>
                    {i > 0 && <Divider />}
                    <Opinion resena={r} garajeId={garajeId} alResponder={actualizar} />
                  </Box>
                ))}
                {datos.next && (
                  <Button onClick={masOpiniones} disabled={cargandoMas} sx={{ mt: 1 }}>{cargandoMas ? 'Cargando…' : 'Ver más'}</Button>
                )}
              </Box>
            )}
          </Seccion>
        </>
      )}
    </>
  );
}
