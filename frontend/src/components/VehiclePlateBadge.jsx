import { Box } from '@mui/material';
import { MONO } from '../theme';

/**
 * Formatea patentes argentinas:
 *  Mercosur auto  AA123BB -> AA 123 BB
 *  Mercosur moto  A123BCD -> A 123 BCD
 *  Formato viejo  ABC123  -> ABC 123
 */
export function formatPatente(raw = '') {
  const p = raw.replace(/[\s-]/g, '').toUpperCase();
  let m;
  if ((m = p.match(/^([A-Z]{2})(\d{3})([A-Z]{2})$/))) return `${m[1]} ${m[2]} ${m[3]}`;
  if ((m = p.match(/^([A-Z])(\d{3})([A-Z]{3})$/))) return `${m[1]} ${m[2]} ${m[3]}`;
  if ((m = p.match(/^([A-Z]{3})(\d{3})$/))) return `${m[1]} ${m[2]}`;
  return p;
}

export default function VehiclePlateBadge({ patente, sinBorde = false }) {
  return (
    <Box
      component="span"
      aria-label={`Patente ${patente}`}
      sx={{
        display: 'inline-block', flexShrink: 0, whiteSpace: 'nowrap', fontFamily: MONO, fontSize: 14, fontWeight: 700, letterSpacing: '0.06em',
        ...(sinBorde ? {} : { px: 1, py: 0.25, border: '1.5px solid', borderColor: 'text.primary', borderRadius: 1.5 }),
      }}
    >
      {formatPatente(patente)}
    </Box>
  );
}
