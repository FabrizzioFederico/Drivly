import { Alert, Box, Card, CardContent, Stack, Typography } from '@mui/material';

/** Título de la sección, con sus acciones a la derecha. */
export function Encabezado({ titulo, detalle, children }) {
  return (
    <Stack direction="row" sx={{ flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
      <Box>
        <Typography variant="h1">{titulo}</Typography>
        {detalle && <Typography variant="body2" sx={{ color: 'text.secondary' }}>{detalle}</Typography>}
      </Box>
      {children}
    </Stack>
  );
}

/** Mensaje de resultado: { ok: true | false | null, text }. null = en proceso. */
export function Aviso({ msg }) {
  if (!msg) return null;
  const severity = msg.ok === true ? 'success' : msg.ok === false ? 'error' : 'info';
  return <Alert severity={severity}>{msg.text}</Alert>;
}

/** Tarjeta con título y contenido apilado. */
export function Seccion({ titulo, detalle, accion, sx, children }) {
  return (
    <Card sx={sx}>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 3, '&:last-child': { pb: 3 } }}>
        <Stack direction="row" sx={{ flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: 1 }}>
          <Box>
            <Typography variant="h2">{titulo}</Typography>
            {detalle && <Typography variant="body2" sx={{ color: 'text.secondary' }}>{detalle}</Typography>}
          </Box>
          {accion}
        </Stack>
        {children}
      </CardContent>
    </Card>
  );
}

export function Leyenda({ color, children }) {
  return (
    <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
      <Box sx={{ width: 10, height: 10, borderRadius: 0.25, bgcolor: color }} />
      <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>{children}</Typography>
    </Stack>
  );
}
