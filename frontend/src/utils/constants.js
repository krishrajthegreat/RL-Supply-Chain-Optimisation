/* Node geographic coordinates → SVG positions (Mercator) */
export const NODE_COORDS = {
  shanghai_port:  { lat: 31.23, lng: 121.47, label: 'Shanghai',   type: 'port' },
  rotterdam_port: { lat: 51.91, lng: 4.48,   label: 'Rotterdam',  type: 'port' },
  hamburg_port:   { lat: 53.55, lng: 9.99,   label: 'Hamburg',    type: 'port' },
  singapore_port: { lat: 1.29,  lng: 103.85, label: 'Singapore',  type: 'port' },
  la_port:        { lat: 33.74, lng:-118.27,  label: 'Los Angeles',type: 'port' },
  frankfurt_dc:   { lat: 50.03, lng: 8.57,   label: 'Frankfurt',  type: 'dc' },
  london_dc:      { lat: 51.50, lng: 0.05,   label: 'London',     type: 'dc' },
  paris_dc:       { lat: 48.86, lng: 2.35,   label: 'Paris',      type: 'dc' },
  newyork_dc:     { lat: 40.68, lng:-74.04,  label: 'New York',   type: 'dc' },
  chicago_dc:     { lat: 41.88, lng:-87.62,  label: 'Chicago',    type: 'dc' },
  dubai_hub:      { lat: 25.27, lng: 55.29,  label: 'Dubai',      type: 'hub' },
  mumbai_hub:     { lat: 19.02, lng: 72.85,  label: 'Mumbai',     type: 'hub' },
  tokyo_hub:      { lat: 35.45, lng: 139.77, label: 'Tokyo',      type: 'hub' },
  seoul_hub:      { lat: 37.46, lng: 126.62, label: 'Seoul',      type: 'hub' },
  sydney_dc:      { lat:-33.85, lng: 151.21, label: 'Sydney',     type: 'dc' },
};

/* Convert lat/lng to SVG x/y using Mercator projection */
export function toSVG(lat, lng, width = 1000, height = 500) {
  const x = ((lng + 180) / 360) * width;
  const latRad = (lat * Math.PI) / 180;
  const mercN = Math.log(Math.tan(Math.PI / 4 + latRad / 2));
  const y = height / 2 - (mercN / Math.PI) * (height / 2);
  return { x, y };
}

/* Risk status from score */
export function riskStatus(score) {
  if (score >= 0.75) return 'red';
  if (score >= 0.55) return 'amber';
  return 'green';
}

/* Risk color */
export function riskColor(score) {
  if (score >= 0.75) return '#f87171';
  if (score >= 0.55) return '#fbbf24';
  return '#34d399';
}

/* Node icon by type */
export function nodeIcon(type) {
  switch (type) {
    case 'port': return '\u2693'; // anchor
    case 'hub':  return '\u2B22'; // hexagon
    case 'dc':   return '\u25A0'; // square
    default:     return '\u25CF'; // circle
  }
}

/* Format hours to human readable */
export function fmtHours(h) {
  if (h < 24) return `${Math.round(h)}h`;
  const d = Math.floor(h / 24);
  const rem = Math.round(h % 24);
  return rem > 0 ? `${d}d ${rem}h` : `${d}d`;
}

export const EDGE_PAIRS = [
  ['shanghai_port', 'singapore_port'], ['shanghai_port', 'tokyo_hub'],
  ['shanghai_port', 'seoul_hub'], ['shanghai_port', 'la_port'],
  ['rotterdam_port', 'hamburg_port'], ['rotterdam_port', 'frankfurt_dc'],
  ['rotterdam_port', 'london_dc'], ['rotterdam_port', 'paris_dc'],
  ['hamburg_port', 'frankfurt_dc'], ['hamburg_port', 'london_dc'],
  ['singapore_port', 'dubai_hub'], ['singapore_port', 'mumbai_hub'],
  ['singapore_port', 'rotterdam_port'], ['singapore_port', 'sydney_dc'],
  ['la_port', 'chicago_dc'], ['la_port', 'newyork_dc'],
  ['frankfurt_dc', 'paris_dc'], ['london_dc', 'newyork_dc'],
  ['dubai_hub', 'mumbai_hub'], ['dubai_hub', 'frankfurt_dc'],
  ['dubai_hub', 'rotterdam_port'], ['mumbai_hub', 'singapore_port'],
  ['mumbai_hub', 'dubai_hub'], ['tokyo_hub', 'la_port'],
  ['tokyo_hub', 'seoul_hub'], ['seoul_hub', 'shanghai_port'],
  ['newyork_dc', 'chicago_dc'], ['chicago_dc', 'la_port'],
  ['sydney_dc', 'singapore_port'], ['sydney_dc', 'tokyo_hub'],
];
