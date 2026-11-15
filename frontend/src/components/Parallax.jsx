import { useEffect, useRef } from 'react';
import { Box } from '@mui/material';

/*
 * Efecto parallax: cada capa se mueve a otra velocidad que el scroll y eso da la ilusión de profundidad.
 * Un IntersectionObserver anota qué capas están en pantalla y sólo esas se recalculan en cada cuadro
 * (un requestAnimationFrame por scroll, y sólo se escribe `transform`: no recalcula el layout).
 * Quien pidió menos movimiento en el sistema ve las capas quietas.
 */
const visibles = new Set();
const datos = new WeakMap(); // capa -> profundidad
let pendiente = false;
let observador = null;

function actualizar() {
  pendiente = false;
  const alto = window.innerHeight;
  for (const el of visibles) {
    // Se mide el contenedor (que no se mueve), no la capa: así no se retroalimenta con su propio transform
    const caja = el.parentElement.getBoundingClientRect();
    const desvio = caja.top + caja.height / 2 - alto / 2; // 0 cuando el contenedor está centrado en la pantalla
    el.style.transform = `translate3d(0, ${(-desvio * datos.get(el)).toFixed(1)}px, 0)`;
  }
}

function pedirCuadro() {
  if (!pendiente) {
    pendiente = true;
    requestAnimationFrame(actualizar);
  }
}

function registrar(el, profundidad) {
  if (!observador) {
    observador = new IntersectionObserver((entradas) => {
      for (const e of entradas) {
        for (const capa of e.target.__capas ?? []) {
          if (e.isIntersecting) visibles.add(capa);
          else visibles.delete(capa);
        }
      }
      pedirCuadro();
    }, { rootMargin: '25% 0px' }); // un poco antes de entrar, para que no "salte" al aparecer
    window.addEventListener('scroll', pedirCuadro, { passive: true });
    window.addEventListener('resize', pedirCuadro);
  }
  datos.set(el, profundidad);
  // Se observa el contenedor (es el que entra y sale de la pantalla); varias capas pueden compartirlo
  const contenedor = el.parentElement;
  contenedor.__capas ??= new Set();
  contenedor.__capas.add(el);
  observador.unobserve(contenedor); // re-observar dispara un aviso nuevo con el estado actual de todas sus capas
  observador.observe(contenedor);
  return () => {
    contenedor.__capas.delete(el);
    if (contenedor.__capas.size === 0) observador.unobserve(contenedor);
    visibles.delete(el);
  };
}

const sinMovimiento = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/**
 * Capa que se desplaza con profundidad.
 *   profundidad > 0: está "más lejos", se mueve más lento que la página (fondos).
 *   profundidad < 0: está "más cerca", se mueve más rápido (elementos que flotan adelante).
 * Va dentro de un contenedor con position: relative; por defecto ocupa todo el contenedor.
 * `soloEscritorio`: en pantallas angostas queda quieta (ahí el contenido va apilado y podría encimarse).
 */
export function Capa({ profundidad, sx, children, decorativa = true, soloEscritorio = false, ...resto }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || sinMovimiento() || (soloEscritorio && window.matchMedia?.('(max-width: 899px)').matches)) return undefined;
    return registrar(el, profundidad);
  }, [profundidad, soloEscritorio]);

  return (
    <Box
      ref={ref}
      aria-hidden={decorativa || undefined}
      sx={{
        ...(decorativa ? { position: 'absolute', inset: 0, pointerEvents: 'none' } : { position: 'relative' }),
        willChange: 'transform',
        ...sx,
      }}
      {...resto}
    >
      {children}
    </Box>
  );
}
