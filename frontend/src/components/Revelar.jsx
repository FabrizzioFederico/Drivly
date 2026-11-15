import { useEffect, useRef, useState } from 'react';
import { Box } from '@mui/material';

const sinMovimiento = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/*
 * Un único IntersectionObserver para toda la página: avisa cuando cada elemento entra en la pantalla.
 * Se dispara un poco antes de que aparezca entero (15 % visible y 60 px antes del borde de abajo).
 */
const avisos = new Map();
let observador = null;

function observar(el, alVer) {
  if (!observador) {
    observador = new IntersectionObserver((entradas) => {
      for (const e of entradas) {
        if (!e.isIntersecting) continue;
        avisos.get(e.target)?.();
        observador.unobserve(e.target); // se anima una sola vez
        avisos.delete(e.target);
      }
    }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });
  }
  avisos.set(el, alVer);
  observador.observe(el);
  return () => {
    observador.unobserve(el);
    avisos.delete(el);
  };
}

/**
 * Aparece con profundidad al entrar en la pantalla: viene de más abajo, de más lejos (más chico e inclinado hacia
 * atrás) y transparente. `retraso` (ms) escalona los elementos de una misma fila.
 * Con "reducir movimiento" en el sistema se ve directamente, sin animación.
 */
export default function Revelar({ children, retraso = 0, sx, ...resto }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(sinMovimiento);

  useEffect(() => {
    if (visible || !ref.current) return undefined;
    return observar(ref.current, () => setVisible(true));
  }, [visible]);

  return (
    <Box
      ref={ref}
      sx={{
        height: '100%',
        opacity: visible ? 1 : 0,
        transform: visible ? 'none' : 'perspective(900px) translate3d(0, 56px, -80px) rotateX(10deg)',
        transformOrigin: '50% 100%',
        transition: 'opacity 700ms ease, transform 900ms cubic-bezier(0.16, 1, 0.3, 1)',
        transitionDelay: `${retraso}ms`,
        ...sx,
      }}
      {...resto}
    >
      {children}
    </Box>
  );
}
