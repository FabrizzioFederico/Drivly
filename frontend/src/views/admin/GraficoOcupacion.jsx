import { Box } from '@mui/material';
import {
  BarController, BarElement, CategoryScale, Chart as ChartJS, LinearScale, LineController, LineElement, PointElement, Tooltip,
} from 'chart.js';
import { Chart } from 'react-chartjs-2';
import { MONO, T } from '../../theme';

ChartJS.register(BarController, BarElement, CategoryScale, LinearScale, LineController, LineElement, PointElement, Tooltip);

// Colores validados contra la superficie oscura (#151517): banda de luminosidad, croma y separación para daltonismo.
// Teal = la marca; violeta para que "sin reserva" no se confunda con el ámbar de la línea de alerta (color de estado).
export const SERIE_APP = '#009E89';
export const SERIE_PRESENCIAL = '#9a6ee0';
const ALTO = 260;

const porcentaje = (n, total) => `${Math.round((n / (total || 1)) * 100)} %`;
const hh = (h) => `${String(h).padStart(2, '0')}:00`;

/** Ocupación por franja horaria: barras apiladas (app y abonos + sin reserva) contra la línea de alerta. */
export default function GraficoOcupacion({ ocupacion }) {
  const total = ocupacion?.capacidad ?? 0;
  const umbral = Math.round(total * (ocupacion?.umbral_alerta ?? 0.9));
  const franjas = ocupacion?.franjas ?? [];
  const ahora = new Date().getHours();
  // Las horas que todavía no pasaron son proyección: se dibujan más tenues
  const tenue = (color, i) => (franjas[i]?.proyectada ? `${color}73` : color);

  const datos = {
    labels: franjas.map((f) => hh(f.hora)),
    datasets: [
      {
        type: 'bar', label: 'App y abonos', data: franjas.map((f) => f.app), stack: 'ocupacion', order: 2,
        backgroundColor: franjas.map((_, i) => tenue(SERIE_APP, i)),
        hoverBackgroundColor: SERIE_APP, // al pasar el mouse se ve el color pleno, sin el brillo que agrega Chart.js
        // Punta redondeada sólo si es el segmento de arriba (no hay clientes sin reserva en esa hora)
        borderRadius: (c) => (franjas[c.dataIndex]?.presencial ? 0 : { topLeft: 4, topRight: 4 }),
        borderSkipped: false,
      },
      {
        type: 'bar', label: 'Sin reserva', data: franjas.map((f) => f.presencial), stack: 'ocupacion', order: 2,
        backgroundColor: franjas.map((_, i) => tenue(SERIE_PRESENCIAL, i)),
        hoverBackgroundColor: SERIE_PRESENCIAL,
        // Separación de 2 px entre segmentos (color de la superficie) y punta redondeada arriba
        borderColor: T['surface-1'], borderWidth: { top: 0, bottom: 2, left: 0, right: 0 }, borderSkipped: false,
        borderRadius: { topLeft: 4, topRight: 4 },
      },
      {
        type: 'line', label: `Alerta ${porcentaje(umbral, total)}`, data: franjas.map(() => umbral), order: 1,
        borderColor: T.warning, borderWidth: 2, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 0, fill: false,
      },
    ],
  };

  const opciones = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    interaction: { mode: 'index', intersect: false }, // tooltip de la franja entera, no de un segmento suelto
    datasets: { bar: { barPercentage: 0.8, categoryPercentage: 0.9 } },
    scales: {
      x: {
        stacked: true,
        grid: { display: false },
        border: { color: T.border },
        ticks: {
          color: (c) => (franjas[c.index]?.hora === ahora ? T['text-primary'] : T['text-muted']),
          font: (c) => ({ family: MONO, size: 11, weight: franjas[c.index]?.hora === ahora ? 800 : 400 }),
          maxRotation: 0, autoSkip: true,
          callback: (_, i) => String(franjas[i]?.hora ?? '').padStart(2, '0'),
        },
      },
      y: {
        stacked: true, beginAtZero: true, max: total || undefined,
        grid: { color: `${T.border}99`, drawTicks: false },
        border: { display: false },
        ticks: { color: T['text-muted'], font: { size: 11 }, padding: 8, precision: 0, maxTicksLimit: 5 },
      },
    },
    plugins: {
      legend: { display: false }, // la leyenda va en HTML, arriba del gráfico
      tooltip: {
        backgroundColor: T['surface-2'], borderColor: T.border, borderWidth: 1, padding: 10,
        titleColor: T['text-primary'], bodyColor: T['text-primary'], footerColor: T['text-muted'],
        boxPadding: 4, usePointStyle: true,
        filter: (item) => item.dataset.type === 'bar',
        callbacks: {
          title: (items) => {
            const f = franjas[items[0]?.dataIndex];
            return f ? `${hh(f.hora)} · ${f.hora === ahora ? 'ahora' : f.proyectada ? 'proyección' : 'real'}` : '';
          },
          label: (item) => ` ${item.dataset.label}: ${item.raw}`,
          footer: (items) => {
            const f = franjas[items[0]?.dataIndex];
            if (!f) return '';
            const ocupados = f.app + f.presencial;
            return `${ocupados} de ${total} lugares (${porcentaje(ocupados, total)})${ocupados >= umbral ? ' · supera la alerta' : ''}`;
          },
        },
      },
    },
  };

  const actual = franjas.find((f) => f.hora === ahora);
  const resumen = actual
    ? `Ocupación por hora. Ahora, ${hh(ahora)}: ${actual.app} lugares de app y abonos y ${actual.presencial} sin reserva, de ${total}. Alerta en ${umbral}.`
    : `Ocupación por hora, capacidad ${total}, alerta en ${umbral}.`;

  return (
    <Box sx={{ height: ALTO, position: 'relative' }}>
      <Chart type="bar" data={datos} options={opciones} aria-label={resumen} role="img" />
    </Box>
  );
}
