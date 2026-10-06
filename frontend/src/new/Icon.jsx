// The ONE icon set of the dashboard: inline SVG, 24 x 24 grid, stroke 1.5, round ends, drawn in the colour of the text around it (currentColor).
// Icons are decoration: they are hidden from screen readers (aria-hidden) and always sit next to a word or inside a button that has a text or aria-label.
// The list is written down in docs/VISUAL_STYLE.md.
const PATHS = {
  map: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14',
  cloud: 'M7 18h10.2a4 4 0 0 0 .6-7.95A5.5 5.5 0 0 0 7.2 9.3 4.4 4.4 0 0 0 7 18z',
  clipboard: 'M9 4h6v3H9zM7 5.5H6.5a1.5 1.5 0 0 0-1.5 1.5v13A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V7a1.5 1.5 0 0 0-1.5-1.5H17M9 12h6M9 16h4',
  bars: 'M5 20V11M12 20V4M19 20v-6',
  close: 'M6 6l12 12M18 6 6 18',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  ring: 'M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z',
  triangle: 'M12 4.5 20.5 19h-17z',
  down: 'M6 9l6 6 6-6',
  up: 'M6 15l6-6 6 6',
  right: 'M9 6l6 6-6 6',
  left: 'M15 6l-6 6 6 6',
  warn: 'M12 4.5 20.5 19h-17zM12 10v4M12 16.6v.01',
  flag: 'M6 21V4M6 5h11l-2 4 2 4H6',
  dotring: 'M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4',
  rain: 'M4 12a8 8 0 0 1 16 0zM12 12v6a2 2 0 0 0 4 0',
  wave: 'M3 9c3-3 6 3 9 0s6 3 9 0M3 15c3-3 6 3 9 0s6 3 9 0',
  clock: 'M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 8v4l3 2',
  calendar: 'M4 6.5h16V20H4zM4 10.5h16M8 4v4M16 4v4',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
  target: 'M12 3v4M12 17v4M3 12h4M17 12h4M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  grid: 'M4 4h16v16H4zM4 12h16M12 4v16',
  tree: 'M12 21v-6M12 15c-4 0-6.5-3-6.5-6S8 4 12 4s6.5 2 6.5 5-2.5 6-6.5 6z',
  undo: 'M9 8H4V3M4 8a9 9 0 1 1-1 7',
  layers: 'M12 3 3 8l9 5 9-5zM3 13l9 5 9-5',
  legend: 'M4 7h3M10 7h10M4 12h3M10 12h10M4 17h3M10 17h10',
  download: 'M12 4v11M7 11l5 5 5-5M5 20h14',
  dot: 'M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z',
  half: 'M12 4a8 8 0 1 0 0 16zM12 4a8 8 0 0 1 0 16',
  pin: 'M12 21s-6-5.5-6-10a6 6 0 1 1 12 0c0 4.5-6 10-6 10zM12 8.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z',
  info: 'M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 11v5M12 8v.01',
  dash: 'M7 12h10',
  question: 'M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17v.01',
  panel: 'M4 5h16v14H4zM9 5v14',
}
const FILLED = new Set(['dot'])

// <Icon name="check" /> ; size in px (16 by default; 20 for tabs and big buttons)
export default function Icon({ name, size = 16, className = '' }) {
  const d = PATHS[name]
  if (!d) return null
  return (
    <svg
      className={`nw-icon ${className}`}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill={FILLED.has(name) ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray={name === 'dotring' ? '1.6 2.6' : undefined}
      aria-hidden="true"
      focusable="false"
    >
      <path d={d} />
    </svg>
  )
}

