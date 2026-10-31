import { Box } from '@mui/material';
import { keyframes } from '@mui/material/styles';

// fondo y color de cada estado
const COLORES = {
  HOLD: ['var(--warning-soft)', 'var(--warning)'],
  CONFIRMADA: ['var(--success-soft)', 'var(--success)'],
  EN_CURSO: ['var(--accent-soft)', 'var(--accent)'],
  CON_DEUDA: ['var(--danger-soft)', 'var(--danger)'],
  SIN_LUGAR: ['var(--danger-soft)', 'var(--danger)'],
  FINALIZADA: ['var(--surface-2)', 'var(--text-muted)'],
};

const LABEL = {
  HOLD: 'HOLD', CONFIRMADA: 'CONFIRMADA', EN_CURSO: 'EN CURSO', CON_DEUDA: 'CON DEUDA', FINALIZADA: 'FINALIZADA',
  EXPIRADA: 'EXPIRADA', CANCELADA: 'CANCELADA', NO_SHOW: 'NO SE PRESENTÓ', SIN_LUGAR: 'SIN LUGAR',
};

const pulso = keyframes`
  from { transform: scale(1); opacity: .75; }
  to { transform: scale(2.2); opacity: 0; }
`;

/** Estado de una reserva. HOLD y CON_DEUDA llevan punto pulsante para llamar la atención. */
export default function StatusBadge({ estado }) {
  const [fondo, color] = COLORES[estado] ?? COLORES.FINALIZADA;
  const pulsa = estado === 'HOLD' || estado === 'CON_DEUDA';
  return (
    <Box component="span" role="status" sx={{ display: 'inline-flex', alignItems: 'center', gap: 1, height: 28, px: 1.5, borderRadius: 14, bgcolor: fondo, color, fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>
      <Box component="span" sx={{ position: 'relative', width: 8, height: 8, borderRadius: '50%', bgcolor: color }}>
        {pulsa && <Box component="span" sx={{ position: 'absolute', inset: 0, borderRadius: '50%', bgcolor: color, animation: `${pulso} 1s ease-out infinite` }} />}
      </Box>
      {LABEL[estado] ?? estado}
    </Box>
  );
}
