/* Network topology data from the NEXUS backend (nodes.json / shipments.json) */

export interface NetworkNode {
  id: string; name: string; type: 'port'|'dc'|'hub'; region: string; country: string
  lat: number; lng: number; throughput_capacity: number; current_queue_depth: number
  avg_dwell_hours: number; health_score: number; circuit_state: 'closed'|'open'|'half_open'
  weather_severity: number; congestion_score: number
}

export interface NetworkEdge {
  from: string; to: string; mode: 'sea'|'road'|'rail'|'air'
  transit_hours: number; cost_per_teu: number; carbon_kg_per_teu: number
  reliability_score: number; geopolitical_risk_score: number; capacity_utilization: number
}

export interface Shipment {
  shipment_id: string; origin: string; destination: string; cargo_type: string
  value_usd: number; weight_tonnes: number; sla_deadline_hours: number
  current_node: string; current_carrier: string; route_planned: string[]
  status: string; priority_tier: number
}

export type AgentName = 'SENTINEL'|'GUARDIAN'|'NAVIGATOR'|'STOCKPILE'|'BROKER'|'HERALD'

export interface AgentEvent {
  id: string; agent: AgentName; message: string; timestamp: string; severity: 'info'|'warn'|'critical'
}

export interface RerouteOption {
  label: string; route: string[]; transit_hours: number; cost_usd: number
  carbon_kg: number; reliability: number; green_resilience: number; selected: boolean
}

export interface RerouteAnalysis {
  shipment_id: string; cargo_type: string; origin: string; destination: string
  blocked_node: string; original_route: string[]; options: RerouteOption[]
  rationale: string
}

export const AGENT_COLORS: Record<AgentName, string> = {
  SENTINEL: '#5ed29c', GUARDIAN: '#f5a623', NAVIGATOR: '#5e9ed2',
  STOCKPILE: '#d25ed2', BROKER: '#d2c45e', HERALD: '#d27a5e',
}

// ── 15 Nodes ──
export const INITIAL_NODES: NetworkNode[] = [
  { id:'shanghai_port', name:'Port of Shanghai', type:'port', region:'east_asia', country:'CN', lat:31.2304, lng:121.4737, throughput_capacity:4700, current_queue_depth:12, avg_dwell_hours:48, health_score:0.92, circuit_state:'closed', weather_severity:1.2, congestion_score:0.35 },
  { id:'rotterdam_port', name:'Port of Rotterdam', type:'port', region:'northern_europe', country:'NL', lat:51.9225, lng:4.47917, throughput_capacity:3800, current_queue_depth:8, avg_dwell_hours:36, health_score:0.95, circuit_state:'closed', weather_severity:2.0, congestion_score:0.22 },
  { id:'hamburg_port', name:'Port of Hamburg', type:'port', region:'northern_europe', country:'DE', lat:53.5511, lng:9.9937, throughput_capacity:2600, current_queue_depth:15, avg_dwell_hours:42, health_score:0.88, circuit_state:'closed', weather_severity:2.5, congestion_score:0.41 },
  { id:'singapore_port', name:'Port of Singapore', type:'port', region:'southeast_asia', country:'SG', lat:1.2644, lng:103.8222, throughput_capacity:3900, current_queue_depth:6, avg_dwell_hours:30, health_score:0.97, circuit_state:'closed', weather_severity:1.0, congestion_score:0.18 },
  { id:'la_port', name:'Port of Los Angeles', type:'port', region:'north_america_west', country:'US', lat:33.7395, lng:-118.2673, throughput_capacity:3100, current_queue_depth:18, avg_dwell_hours:54, health_score:0.84, circuit_state:'closed', weather_severity:0.8, congestion_score:0.48 },
  { id:'frankfurt_dc', name:'Frankfurt DC', type:'dc', region:'central_europe', country:'DE', lat:50.1109, lng:8.6821, throughput_capacity:1800, current_queue_depth:3, avg_dwell_hours:18, health_score:0.93, circuit_state:'closed', weather_severity:1.5, congestion_score:0.12 },
  { id:'london_dc', name:'London DC', type:'dc', region:'northern_europe', country:'GB', lat:51.5074, lng:-0.1278, throughput_capacity:1500, current_queue_depth:4, avg_dwell_hours:20, health_score:0.91, circuit_state:'closed', weather_severity:1.8, congestion_score:0.15 },
  { id:'paris_dc', name:'Paris DC', type:'dc', region:'western_europe', country:'FR', lat:48.8566, lng:2.3522, throughput_capacity:1400, current_queue_depth:2, avg_dwell_hours:16, health_score:0.94, circuit_state:'closed', weather_severity:1.3, congestion_score:0.10 },
  { id:'newyork_dc', name:'New York DC', type:'dc', region:'north_america_east', country:'US', lat:40.7128, lng:-74.006, throughput_capacity:2200, current_queue_depth:7, avg_dwell_hours:22, health_score:0.90, circuit_state:'closed', weather_severity:1.6, congestion_score:0.25 },
  { id:'chicago_dc', name:'Chicago DC', type:'dc', region:'north_america_central', country:'US', lat:41.8781, lng:-87.6298, throughput_capacity:1900, current_queue_depth:5, avg_dwell_hours:19, health_score:0.92, circuit_state:'closed', weather_severity:2.2, congestion_score:0.19 },
  { id:'dubai_hub', name:'Dubai Hub', type:'hub', region:'middle_east', country:'AE', lat:25.2048, lng:55.2708, throughput_capacity:2800, current_queue_depth:9, avg_dwell_hours:28, health_score:0.93, circuit_state:'closed', weather_severity:0.5, congestion_score:0.30 },
  { id:'mumbai_hub', name:'Mumbai Hub', type:'hub', region:'south_asia', country:'IN', lat:19.076, lng:72.8777, throughput_capacity:2100, current_queue_depth:14, avg_dwell_hours:52, health_score:0.82, circuit_state:'closed', weather_severity:3.0, congestion_score:0.45 },
  { id:'tokyo_hub', name:'Tokyo Hub', type:'hub', region:'east_asia', country:'JP', lat:35.6762, lng:139.6503, throughput_capacity:2400, current_queue_depth:5, avg_dwell_hours:24, health_score:0.96, circuit_state:'closed', weather_severity:1.4, congestion_score:0.14 },
  { id:'seoul_hub', name:'Seoul Hub', type:'hub', region:'east_asia', country:'KR', lat:37.5665, lng:126.978, throughput_capacity:2000, current_queue_depth:4, avg_dwell_hours:22, health_score:0.95, circuit_state:'closed', weather_severity:1.2, congestion_score:0.11 },
  { id:'sydney_dc', name:'Sydney DC', type:'dc', region:'oceania', country:'AU', lat:-33.8688, lng:151.2093, throughput_capacity:1200, current_queue_depth:3, avg_dwell_hours:20, health_score:0.94, circuit_state:'closed', weather_severity:0.9, congestion_score:0.08 },
]

// ── 35 Edges ──
export const INITIAL_EDGES: NetworkEdge[] = [
  { from:'shanghai_port', to:'rotterdam_port', mode:'sea', transit_hours:720, cost_per_teu:2800, carbon_kg_per_teu:580, reliability_score:0.88, geopolitical_risk_score:0.15, capacity_utilization:0.78 },
  { from:'shanghai_port', to:'hamburg_port', mode:'sea', transit_hours:744, cost_per_teu:2950, carbon_kg_per_teu:610, reliability_score:0.86, geopolitical_risk_score:0.18, capacity_utilization:0.72 },
  { from:'shanghai_port', to:'singapore_port', mode:'sea', transit_hours:120, cost_per_teu:650, carbon_kg_per_teu:95, reliability_score:0.95, geopolitical_risk_score:0.05, capacity_utilization:0.82 },
  { from:'shanghai_port', to:'la_port', mode:'sea', transit_hours:336, cost_per_teu:3200, carbon_kg_per_teu:420, reliability_score:0.84, geopolitical_risk_score:0.08, capacity_utilization:0.88 },
  { from:'shanghai_port', to:'tokyo_hub', mode:'sea', transit_hours:72, cost_per_teu:480, carbon_kg_per_teu:62, reliability_score:0.96, geopolitical_risk_score:0.04, capacity_utilization:0.70 },
  { from:'shanghai_port', to:'seoul_hub', mode:'sea', transit_hours:60, cost_per_teu:420, carbon_kg_per_teu:48, reliability_score:0.97, geopolitical_risk_score:0.06, capacity_utilization:0.65 },
  { from:'singapore_port', to:'rotterdam_port', mode:'sea', transit_hours:504, cost_per_teu:2200, carbon_kg_per_teu:410, reliability_score:0.90, geopolitical_risk_score:0.22, capacity_utilization:0.75 },
  { from:'singapore_port', to:'dubai_hub', mode:'sea', transit_hours:168, cost_per_teu:890, carbon_kg_per_teu:135, reliability_score:0.93, geopolitical_risk_score:0.20, capacity_utilization:0.68 },
  { from:'singapore_port', to:'mumbai_hub', mode:'sea', transit_hours:144, cost_per_teu:760, carbon_kg_per_teu:118, reliability_score:0.89, geopolitical_risk_score:0.12, capacity_utilization:0.71 },
  { from:'singapore_port', to:'sydney_dc', mode:'sea', transit_hours:192, cost_per_teu:1100, carbon_kg_per_teu:155, reliability_score:0.94, geopolitical_risk_score:0.03, capacity_utilization:0.55 },
  { from:'rotterdam_port', to:'hamburg_port', mode:'road', transit_hours:6, cost_per_teu:280, carbon_kg_per_teu:42, reliability_score:0.97, geopolitical_risk_score:0.01, capacity_utilization:0.60 },
  { from:'rotterdam_port', to:'frankfurt_dc', mode:'rail', transit_hours:12, cost_per_teu:350, carbon_kg_per_teu:28, reliability_score:0.95, geopolitical_risk_score:0.01, capacity_utilization:0.58 },
  { from:'rotterdam_port', to:'london_dc', mode:'sea', transit_hours:18, cost_per_teu:420, carbon_kg_per_teu:32, reliability_score:0.93, geopolitical_risk_score:0.02, capacity_utilization:0.62 },
  { from:'rotterdam_port', to:'paris_dc', mode:'rail', transit_hours:14, cost_per_teu:380, carbon_kg_per_teu:25, reliability_score:0.94, geopolitical_risk_score:0.01, capacity_utilization:0.52 },
  { from:'hamburg_port', to:'frankfurt_dc', mode:'rail', transit_hours:8, cost_per_teu:220, carbon_kg_per_teu:18, reliability_score:0.96, geopolitical_risk_score:0.01, capacity_utilization:0.55 },
  { from:'hamburg_port', to:'london_dc', mode:'sea', transit_hours:24, cost_per_teu:480, carbon_kg_per_teu:38, reliability_score:0.91, geopolitical_risk_score:0.02, capacity_utilization:0.58 },
  { from:'hamburg_port', to:'paris_dc', mode:'rail', transit_hours:16, cost_per_teu:410, carbon_kg_per_teu:30, reliability_score:0.93, geopolitical_risk_score:0.01, capacity_utilization:0.48 },
  { from:'la_port', to:'newyork_dc', mode:'rail', transit_hours:96, cost_per_teu:1800, carbon_kg_per_teu:165, reliability_score:0.87, geopolitical_risk_score:0.02, capacity_utilization:0.80 },
  { from:'la_port', to:'chicago_dc', mode:'rail', transit_hours:72, cost_per_teu:1400, carbon_kg_per_teu:128, reliability_score:0.89, geopolitical_risk_score:0.02, capacity_utilization:0.76 },
  { from:'dubai_hub', to:'mumbai_hub', mode:'sea', transit_hours:72, cost_per_teu:520, carbon_kg_per_teu:65, reliability_score:0.92, geopolitical_risk_score:0.10, capacity_utilization:0.63 },
  { from:'dubai_hub', to:'rotterdam_port', mode:'sea', transit_hours:336, cost_per_teu:1900, carbon_kg_per_teu:285, reliability_score:0.85, geopolitical_risk_score:0.28, capacity_utilization:0.70 },
  { from:'dubai_hub', to:'frankfurt_dc', mode:'air', transit_hours:8, cost_per_teu:8500, carbon_kg_per_teu:4200, reliability_score:0.98, geopolitical_risk_score:0.05, capacity_utilization:0.45 },
  { from:'mumbai_hub', to:'singapore_port', mode:'sea', transit_hours:144, cost_per_teu:760, carbon_kg_per_teu:118, reliability_score:0.89, geopolitical_risk_score:0.08, capacity_utilization:0.67 },
  { from:'tokyo_hub', to:'la_port', mode:'sea', transit_hours:264, cost_per_teu:2600, carbon_kg_per_teu:340, reliability_score:0.90, geopolitical_risk_score:0.05, capacity_utilization:0.74 },
  { from:'tokyo_hub', to:'seoul_hub', mode:'sea', transit_hours:36, cost_per_teu:310, carbon_kg_per_teu:28, reliability_score:0.97, geopolitical_risk_score:0.08, capacity_utilization:0.50 },
  { from:'seoul_hub', to:'shanghai_port', mode:'sea', transit_hours:48, cost_per_teu:380, carbon_kg_per_teu:38, reliability_score:0.96, geopolitical_risk_score:0.06, capacity_utilization:0.55 },
  { from:'newyork_dc', to:'london_dc', mode:'air', transit_hours:10, cost_per_teu:9200, carbon_kg_per_teu:4600, reliability_score:0.97, geopolitical_risk_score:0.02, capacity_utilization:0.40 },
  { from:'newyork_dc', to:'chicago_dc', mode:'road', transit_hours:14, cost_per_teu:620, carbon_kg_per_teu:85, reliability_score:0.94, geopolitical_risk_score:0.01, capacity_utilization:0.72 },
  { from:'frankfurt_dc', to:'paris_dc', mode:'road', transit_hours:7, cost_per_teu:310, carbon_kg_per_teu:45, reliability_score:0.96, geopolitical_risk_score:0.01, capacity_utilization:0.48 },
  { from:'frankfurt_dc', to:'london_dc', mode:'road', transit_hours:10, cost_per_teu:450, carbon_kg_per_teu:62, reliability_score:0.94, geopolitical_risk_score:0.02, capacity_utilization:0.52 },
  { from:'singapore_port', to:'tokyo_hub', mode:'sea', transit_hours:132, cost_per_teu:950, carbon_kg_per_teu:108, reliability_score:0.93, geopolitical_risk_score:0.04, capacity_utilization:0.66 },
  { from:'shanghai_port', to:'sydney_dc', mode:'sea', transit_hours:240, cost_per_teu:1650, carbon_kg_per_teu:215, reliability_score:0.91, geopolitical_risk_score:0.04, capacity_utilization:0.58 },
  { from:'dubai_hub', to:'london_dc', mode:'air', transit_hours:9, cost_per_teu:8800, carbon_kg_per_teu:4400, reliability_score:0.97, geopolitical_risk_score:0.06, capacity_utilization:0.42 },
  { from:'mumbai_hub', to:'dubai_hub', mode:'sea', transit_hours:72, cost_per_teu:520, carbon_kg_per_teu:65, reliability_score:0.92, geopolitical_risk_score:0.10, capacity_utilization:0.63 },
  { from:'la_port', to:'sydney_dc', mode:'sea', transit_hours:312, cost_per_teu:2100, carbon_kg_per_teu:310, reliability_score:0.89, geopolitical_risk_score:0.03, capacity_utilization:0.50 },
]

// ── Key shipments (subset relevant for demo scenarios) ──
export const INITIAL_SHIPMENTS: Shipment[] = [
  { shipment_id:'SHP-001', origin:'shanghai_port', destination:'frankfurt_dc', cargo_type:'electronics', value_usd:284000, weight_tonnes:18.5, sla_deadline_hours:840, current_node:'shanghai_port', current_carrier:'maersk', route_planned:['shanghai_port','singapore_port','rotterdam_port','frankfurt_dc'], status:'in_transit', priority_tier:1 },
  { shipment_id:'SHP-002', origin:'shanghai_port', destination:'hamburg_port', cargo_type:'automotive_parts', value_usd:520000, weight_tonnes:42, sla_deadline_hours:780, current_node:'singapore_port', current_carrier:'cma_cgm', route_planned:['shanghai_port','singapore_port','hamburg_port'], status:'in_transit', priority_tier:1 },
  { shipment_id:'SHP-003', origin:'rotterdam_port', destination:'chicago_dc', cargo_type:'pharmaceutical', value_usd:1850000, weight_tonnes:6.2, sla_deadline_hours:480, current_node:'rotterdam_port', current_carrier:'hapag_lloyd', route_planned:['rotterdam_port','newyork_dc','chicago_dc'], status:'loading', priority_tier:1 },
  { shipment_id:'SHP-004', origin:'shanghai_port', destination:'la_port', cargo_type:'consumer_goods', value_usd:175000, weight_tonnes:28, sla_deadline_hours:420, current_node:'shanghai_port', current_carrier:'msc', route_planned:['shanghai_port','la_port'], status:'in_transit', priority_tier:2 },
  { shipment_id:'SHP-005', origin:'singapore_port', destination:'london_dc', cargo_type:'textiles', value_usd:92000, weight_tonnes:15, sla_deadline_hours:600, current_node:'dubai_hub', current_carrier:'maersk', route_planned:['singapore_port','dubai_hub','rotterdam_port','london_dc'], status:'in_transit', priority_tier:2 },
  { shipment_id:'SHP-007', origin:'tokyo_hub', destination:'newyork_dc', cargo_type:'electronics', value_usd:715000, weight_tonnes:12, sla_deadline_hours:504, current_node:'tokyo_hub', current_carrier:'one', route_planned:['tokyo_hub','la_port','newyork_dc'], status:'in_transit', priority_tier:1 },
  { shipment_id:'SHP-008', origin:'seoul_hub', destination:'rotterdam_port', cargo_type:'semiconductor', value_usd:2400000, weight_tonnes:3.5, sla_deadline_hours:864, current_node:'shanghai_port', current_carrier:'maersk', route_planned:['seoul_hub','shanghai_port','singapore_port','rotterdam_port'], status:'in_transit', priority_tier:1 },
  { shipment_id:'SHP-014', origin:'hamburg_port', destination:'newyork_dc', cargo_type:'automotive', value_usd:3200000, weight_tonnes:48, sla_deadline_hours:600, current_node:'hamburg_port', current_carrier:'hapag_lloyd', route_planned:['hamburg_port','rotterdam_port','newyork_dc'], status:'loading', priority_tier:1 },
  { shipment_id:'SHP-016', origin:'shanghai_port', destination:'hamburg_port', cargo_type:'furniture', value_usd:135000, weight_tonnes:52, sla_deadline_hours:888, current_node:'shanghai_port', current_carrier:'msc', route_planned:['shanghai_port','singapore_port','dubai_hub','rotterdam_port','hamburg_port'], status:'in_transit', priority_tier:3 },
  { shipment_id:'SHP-022', origin:'shanghai_port', destination:'london_dc', cargo_type:'electronics', value_usd:620000, weight_tonnes:11, sla_deadline_hours:816, current_node:'dubai_hub', current_carrier:'maersk', route_planned:['shanghai_port','singapore_port','dubai_hub','rotterdam_port','london_dc'], status:'in_transit', priority_tier:2 },
  { shipment_id:'SHP-025', origin:'mumbai_hub', destination:'london_dc', cargo_type:'pharmaceutical', value_usd:3800000, weight_tonnes:3, sla_deadline_hours:168, current_node:'dubai_hub', current_carrier:'fedex', route_planned:['mumbai_hub','dubai_hub','london_dc'], status:'in_transit', priority_tier:1 },
  { shipment_id:'SHP-029', origin:'hamburg_port', destination:'paris_dc', cargo_type:'consumer_goods', value_usd:155000, weight_tonnes:22, sla_deadline_hours:48, current_node:'hamburg_port', current_carrier:'dhl', route_planned:['hamburg_port','paris_dc'], status:'in_transit', priority_tier:2 },
]

// ── Pre-computed reroute analyses for demo scenarios ──
export const HAMBURG_REROUTES: RerouteAnalysis[] = [
  {
    shipment_id: 'SHP-002', cargo_type: 'automotive_parts', origin: 'shanghai_port', destination: 'hamburg_port',
    blocked_node: 'hamburg_port', original_route: ['shanghai_port','singapore_port','hamburg_port'],
    rationale: 'Route A is Pareto-optimal: lowest carbon footprint with highest reliability. The Green-Resilience score of 0.74 confirms the carbon-resilience correlation thesis — lower-emission routes are inherently more resilient to disruptions.',
    options: [
      { label:'Route A', route:['shanghai_port','singapore_port','rotterdam_port','frankfurt_dc'], transit_hours:636, cost_usd:3200, carbon_kg:533, reliability:0.93, green_resilience:0.74, selected:true },
      { label:'Route B', route:['shanghai_port','singapore_port','dubai_hub','frankfurt_dc'], transit_hours:296, cost_usd:10040, carbon_kg:4430, reliability:0.91, green_resilience:0.12, selected:false },
      { label:'Route C', route:['shanghai_port','singapore_port','dubai_hub','rotterdam_port','frankfurt_dc'], transit_hours:804, cost_usd:4040, carbon_kg:858, reliability:0.85, green_resilience:0.58, selected:false },
    ],
  },
  {
    shipment_id: 'SHP-014', cargo_type: 'automotive', origin: 'hamburg_port', destination: 'newyork_dc',
    blocked_node: 'hamburg_port', original_route: ['hamburg_port','rotterdam_port','newyork_dc'],
    rationale: 'Direct Rotterdam-to-New York sea route bypasses Hamburg entirely. RL agent prioritised time savings given the platinum SLA tier and $3.2M cargo value.',
    options: [
      { label:'Route A', route:['rotterdam_port','newyork_dc'], transit_hours:504, cost_usd:2200, carbon_kg:410, reliability:0.90, green_resilience:0.72, selected:true },
      { label:'Route B', route:['rotterdam_port','london_dc','newyork_dc'], transit_hours:28, cost_usd:9620, carbon_kg:4632, reliability:0.93, green_resilience:0.08, selected:false },
    ],
  },
  {
    shipment_id: 'SHP-029', cargo_type: 'consumer_goods', origin: 'hamburg_port', destination: 'paris_dc',
    blocked_node: 'hamburg_port', original_route: ['hamburg_port','paris_dc'],
    rationale: 'Rotterdam rail link to Paris offers the best carbon/time tradeoff. RL selected lowest-carbon option given flex SLA tier.',
    options: [
      { label:'Route A', route:['rotterdam_port','paris_dc'], transit_hours:14, cost_usd:380, carbon_kg:25, reliability:0.94, green_resilience:0.89, selected:true },
      { label:'Route B', route:['rotterdam_port','frankfurt_dc','paris_dc'], transit_hours:19, cost_usd:660, carbon_kg:73, reliability:0.93, green_resilience:0.79, selected:false },
    ],
  },
]

// ── Node lookup helper ──
export function getNodeById(nodes: NetworkNode[], id: string): NetworkNode | undefined {
  return nodes.find(n => n.id === id)
}

export function getNodeCoords(nodes: NetworkNode[]): Record<string, [number, number]> {
  const m: Record<string, [number, number]> = {}
  for (const n of nodes) m[n.id] = [n.lng, n.lat]
  return m
}
