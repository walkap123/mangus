export const C = {
  bg: '#1a1a1c',
  card: '#242427',
  fg: '#e8e8ea',
  muted: '#9a9aa2',
  line: '#33333a',
  accent: '#e0803a',
  green: '#4ade80',
  red: '#f66',
  light: '#ebecd0',
  dark: '#6f9350',
  hl: 'rgba(246,240,90,0.55)',
};

// move-class -> label + color
export const CLS: Record<string, { l: string; c: string }> = {
  best: { l: 'Best', c: '#4ade80' },
  good: { l: 'Good', c: '#93c5a0' },
  inaccuracy: { l: 'Inaccuracy', c: '#fbbf24' },
  mistake: { l: 'Mistake', c: '#fb923c' },
  blunder: { l: 'Blunder', c: '#ef4444' },
};

// accuracy -> color grade (green good ... red bad)
export function accColor(acc: number | null | undefined): string {
  if (acc == null) return C.muted;
  if (acc >= 70) return '#4ade80';
  if (acc >= 55) return '#a3e635';
  if (acc >= 40) return '#fbbf24';
  if (acc >= 25) return '#fb923c';
  return '#ef4444';
}

export const resultColor = (r: string) =>
  r === 'win' ? C.green : r === 'loss' ? C.red : C.muted;
