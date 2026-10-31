import { createTheme } from '@mui/material/styles';

// Único lugar con los colores del portal: dark flat, profundidad por capas tonales (bg → surface-1 → surface-2).
// Se publican como variables CSS: en los componentes usar var(--surface-2), var(--text-muted), etc.
const T = {
  bg: '#0B0B0C',
  'surface-1': '#151517',
  'surface-2': '#1E1E21',
  border: '#2A2A2E',
  'border-hover': '#3A3A40',
  'text-primary': '#F5F5F5',
  'text-muted': '#8A8A93',
  accent: '#00C2A8',
  'accent-hover': '#00A892',
  'accent-strong': '#007A6B',
  'accent-soft': '#0F2A27',
  success: '#4ADE80',
  'success-soft': '#12261A',
  danger: '#F43F5E',
  'danger-soft': '#2B1219',
  warning: '#F59E0B',
  'warning-soft': '#2A1F0B',
};

const ANILLO_FOCO = '0 0 0 3px rgba(0,194,168,0.25)';

export const MONO = '"JetBrains Mono", ui-monospace, monospace';

export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: T.accent, dark: T['accent-hover'], contrastText: T.bg },
    secondary: { main: T.accent, dark: T['accent-hover'], contrastText: T.bg },
    success: { main: T.success, contrastText: T.bg },
    warning: { main: T.warning, contrastText: T.bg },
    error: { main: T.danger, contrastText: T.bg },
    info: { main: T.accent, contrastText: T.bg },
    text: { primary: T['text-primary'], secondary: T['text-muted'] },
    divider: T.border,
    background: { default: T.bg, paper: T['surface-1'] },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: 'Inter, system-ui, sans-serif',
    h1: { fontSize: 28, fontWeight: 700, letterSpacing: '-0.01em' },
    h2: { fontSize: 18, fontWeight: 700 },
    h3: { fontSize: 15, fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        ':root': Object.fromEntries(Object.entries(T).map(([k, v]) => [`--${k}`, v])),
        body: { fontVariantNumeric: 'tabular-nums' },
        'input[type=number]': { MozAppearance: 'textfield' },
        'input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button': { WebkitAppearance: 'none', margin: 0 },
      },
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiAppBar: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { backgroundColor: T['surface-1'], color: T['text-primary'], borderBottom: `1px solid ${T.border}` } },
    },
    MuiDrawer: { styleOverrides: { paper: { backgroundColor: T['surface-1'], borderRight: `1px solid ${T.border}` } } },
    MuiCard: {
      defaultProps: { variant: 'outlined' },
      styleOverrides: { root: { borderRadius: 12, backgroundColor: T['surface-1'], borderColor: T.border, boxShadow: 'none' } },
    },
    MuiDialog: { styleOverrides: { paper: { border: `1px solid ${T.border}`, borderRadius: 12, boxShadow: 'none' } } },
    MuiMenu: { styleOverrides: { paper: { border: `1px solid ${T.border}`, boxShadow: 'none' } } },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { minHeight: 40, paddingInline: 16, borderRadius: 8, '&.Mui-disabled': { opacity: 0.4 } },
        contained: { '&.Mui-disabled': { backgroundColor: T.accent, color: T.bg } },
        outlined: {
          borderColor: T.border,
          color: T['text-primary'],
          '&:hover': { backgroundColor: T['surface-2'], borderColor: T.border },
          '&.Mui-disabled': { borderColor: T.border, color: T['text-primary'] },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: T['surface-2'],
          borderRadius: 8,
          '& .MuiOutlinedInput-notchedOutline': { borderColor: T.border },
          '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: T['border-hover'] },
          '&.Mui-focused': { boxShadow: ANILLO_FOCO },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: T.accent, borderWidth: 1 },
          '&.Mui-error .MuiOutlinedInput-notchedOutline': { borderColor: T.danger },
        },
        input: { '&::placeholder': { color: T['text-muted'], opacity: 1 } },
      },
    },
    MuiInputAdornment: { styleOverrides: { root: { color: T['text-muted'], '& .MuiTypography-root': { color: T['text-muted'] } } } },
    MuiSelect: { styleOverrides: { icon: { color: T['text-muted'] } } },
    MuiFormHelperText: { styleOverrides: { root: { fontSize: 12, marginInline: 0 } } },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottomColor: T.border },
        head: { fontSize: 13, fontWeight: 600, color: T['text-muted'], backgroundColor: T['surface-2'] },
      },
    },
    MuiTableRow: { styleOverrides: { root: { '&.MuiTableRow-hover:hover': { backgroundColor: T['surface-2'] } } } },
    MuiListItemIcon: { styleOverrides: { root: { color: 'inherit' } } },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          position: 'relative',
          overflow: 'hidden',
          borderRadius: 8,
          color: T['text-muted'],
          '&:hover': { backgroundColor: T['surface-2'] },
          '&.Mui-selected, &.Mui-selected:hover': { backgroundColor: T['accent-soft'], color: T.accent },
          '&.Mui-selected::before': { content: '""', position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, backgroundColor: T.accent },
        },
      },
    },
  },
});
