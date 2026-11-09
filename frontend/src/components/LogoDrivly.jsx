import { Box } from '@mui/material';

/**
 * Logo de Drivly: la "D" con el auto sobre fondo negro, en baldosa redondeada.
 * El archivo sale de branding/logo-drivly-original.jpg (frontend/public/logo-drivly.png, 256 px).
 */
export default function LogoDrivly({ tamano = 32, sx }) {
  return (
    <Box
      component="img"
      src="/logo-drivly.png"
      alt="Drivly"
      width={tamano}
      height={tamano}
      sx={{ display: 'block', flexShrink: 0, borderRadius: `${Math.round(tamano * 0.22)}px`, ...sx }}
    />
  );
}
