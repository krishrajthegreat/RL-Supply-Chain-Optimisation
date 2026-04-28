/* API base URL — proxied through Vite in dev */
const BASE = '/api/v1';

export async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
  return res.json();
}

export async function post(path, body = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
  return res.json();
}

/* ── Simulation ─────────────────────────────────────── */
export const simStatus      = () => get('/simulation/status');
export const simReset       = (cfg) => post('/simulation/reset', cfg);
export const simStep        = (n = 1) => post(`/simulation/step?n=${n}`);
export const simStart       = (speed = 1) => post(`/simulation/start?speed=${speed}`);
export const simStop        = () => post('/simulation/stop');

/* ── Network ────────────────────────────────────────── */
export const getState       = () => get('/network/state');
export const getNodes       = () => get('/network/nodes');
export const getNode        = (id) => get(`/network/nodes/${id}`);
export const getEdges       = () => get('/network/edges');
export const getPaths       = (o, d, k = 3) => get(`/network/paths/${o}/${d}?k=${k}`);
export const getShipments   = () => get('/network/shipments');
export const getCarriers    = () => get('/network/carriers');

/* ── Disruptions ────────────────────────────────────── */
export const injectScenario = (name) => post(`/disruption/scenario/${name}`);
export const getActive      = () => get('/disruption/active');
export const getHistory     = () => get('/disruption/history');
export const injectWeather  = (body) => post('/disruption/inject/weather', body);

/* ── SENTINEL ───────────────────────────────────────── */
export const getRiskReport  = () => get('/sentinel/risk-report');
export const getNodeRisk    = (id) => get(`/sentinel/risk/${id}`);
export const getOSINT       = () => get('/sentinel/osint');
export const triggerOSINT   = () => post('/sentinel/osint/scan');
export const getFinancial   = () => get('/sentinel/financial');
export const triggerFinScan = () => post('/sentinel/financial/scan');
export const getDecisions   = (n = 20) => get(`/sentinel/decisions?n=${n}`);
export const getSupplierMap = () => get('/sentinel/supplier-risk-map');
