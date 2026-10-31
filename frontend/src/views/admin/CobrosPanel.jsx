import { useEffect, useState } from 'react';
import { Button, Stack, Typography } from '@mui/material';
import { pagosService } from '../../api/pagosService';
import { Aviso, Encabezado, Seccion } from './comun';

/** Cobros — conexión de la cuenta de Mercado Pago (split de pagos, sección 7.2) */
export default function CobrosPanel({ garajeId, retorno }) {
  const [estado, setEstado] = useState(null);
  const [conectando, setConectando] = useState(false);
  const [msg, setMsg] = useState(
    retorno === 'ok' ? { ok: true, text: '¡Cuenta conectada! Los pagos de tus reservas se acreditan en tu Mercado Pago.' }
      : retorno === 'error' ? { ok: false, text: 'No se pudo conectar la cuenta. Intentá nuevamente; si el problema sigue, escribinos a soporte.' }
        : null,
  );

  useEffect(() => {
    pagosService.estadoMercadoPago(garajeId).then(setEstado).catch((e) => setMsg({ ok: false, text: e.message }));
  }, [garajeId]);

  const conectar = async () => {
    setConectando(true); setMsg(null);
    try {
      const { url } = await pagosService.conectarMercadoPago(garajeId);
      window.location.href = url; // salimos de la app hacia Mercado Pago
    } catch (e) {
      setMsg({ ok: false, text: `${e.message}. Intentá nuevamente.` });
      setConectando(false);
    }
  };

  return (
    <Stack spacing={2.5} data-mp-marketplace-page="checkout-pro">
      <Encabezado titulo="Cobros" detalle="Cada reserva se cobra en tu cuenta de Mercado Pago. Drivly retiene automáticamente su comisión del 10 %." />
      <Aviso msg={msg} />
      <Seccion titulo="Cuenta de Mercado Pago" sx={{ maxWidth: 720 }}>
        {!estado ? (
          <Typography variant="body2" aria-live="polite" sx={{ color: 'text.secondary' }}>Cargando estado de la conexión…</Typography>
        ) : estado.conectado ? (
          <Typography variant="body2" sx={{ color: 'success.main', fontWeight: 600 }}>
            Conectada{estado.conectada_en ? ` desde el ${new Date(estado.conectada_en).toLocaleDateString('es-AR')}` : ''}. Los conductores ya pueden pagar sus reservas.
          </Typography>
        ) : (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {estado.requiere_reautorizar
              ? 'Mercado Pago pidió volver a autorizar a Drivly. Mientras tanto tu garaje no aparece en las búsquedas de los conductores.'
              : 'Todavía no conectaste tu cuenta. Hasta que lo hagas, tu garaje no aparece en las búsquedas de los conductores.'}
          </Typography>
        )}
        {estado && !estado.conectado && (
          <Button variant="contained" color="secondary" onClick={conectar} disabled={conectando} data-mp-marketplace-connect="oauth" sx={{ alignSelf: 'flex-start' }}>
            {conectando ? 'Redirigiendo a Mercado Pago…' : estado.requiere_reautorizar ? 'Volver a autorizar' : 'Conectar Mercado Pago'}
          </Button>
        )}
      </Seccion>
    </Stack>
  );
}
