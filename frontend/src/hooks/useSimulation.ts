import { useState, useCallback, useRef } from 'react'
import {
  type NetworkNode, type NetworkEdge, type Shipment, type AgentEvent, type RerouteAnalysis, type AgentName,
  INITIAL_NODES, INITIAL_EDGES, INITIAL_SHIPMENTS, HAMBURG_REROUTES,
} from '@/lib/networkData'

let _evtId = 0
function mkEvent(agent: AgentName, message: string, severity: 'info'|'warn'|'critical' = 'info'): AgentEvent {
  const now = new Date()
  return { id: String(++_evtId), agent, message, severity, timestamp: now.toISOString().slice(11, 19) + 'Z' }
}

export interface SimMetrics {
  totalShipments: number; atRisk: number; circuitOpens: number; reroutes: number; delivered: number
}

export function useSimulation() {
  const [nodes, setNodes] = useState<NetworkNode[]>(() => structuredClone(INITIAL_NODES))
  const [edges] = useState<NetworkEdge[]>(() => structuredClone(INITIAL_EDGES))
  const [shipments, setShipments] = useState<Shipment[]>(() => structuredClone(INITIAL_SHIPMENTS))
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [activeReroute, setActiveReroute] = useState<RerouteAnalysis | null>(null)
  const [metrics, setMetrics] = useState<SimMetrics>({ totalShipments: 12, atRisk: 0, circuitOpens: 0, reroutes: 0, delivered: 0 })
  const [disruptionActive, setDisruptionActive] = useState(false)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  const addEvent = useCallback((e: AgentEvent) => {
    setEvents(prev => [e, ...prev].slice(0, 50))
  }, [])

  const updateNode = useCallback((id: string, patch: Partial<NetworkNode>) => {
    setNodes(prev => prev.map(n => n.id === id ? { ...n, ...patch } : n))
  }, [])

  const scheduleEvent = useCallback((delay: number, fn: () => void) => {
    timers.current.push(setTimeout(fn, delay))
  }, [])

  // ── Hamburg Storm Surge scenario ──
  const injectHamburgStorm = useCallback(() => {
    if (disruptionActive) return
    setDisruptionActive(true)

    // T+0: SENTINEL detects anomalous weather
    addEvent(mkEvent('SENTINEL', 'Anomalous weather pattern detected near Port of Hamburg. Severity: 8.0/10', 'warn'))
    updateNode('hamburg_port', { weather_severity: 8.0, health_score: 0.42 })

    // T+800ms: SENTINEL risk assessment
    scheduleEvent(800, () => {
      addEvent(mkEvent('SENTINEL', 'Risk score for hamburg_port: 0.42 → HIGH. 4 shipments affected: SHP-002, SHP-014, SHP-016, SHP-029', 'critical'))
      updateNode('hamburg_port', { health_score: 0.28 })
      setMetrics(m => ({ ...m, atRisk: 4 }))
    })

    // T+1500ms: GUARDIAN opens circuit
    scheduleEvent(1500, () => {
      addEvent(mkEvent('GUARDIAN', 'Circuit OPENED on hamburg_port — node excluded from all routing. Health: 0.28', 'critical'))
      updateNode('hamburg_port', { circuit_state: 'open', health_score: 0.18, congestion_score: 0.92 })
      setMetrics(m => ({ ...m, circuitOpens: 1 }))
    })

    // T+2500ms: NAVIGATOR computes reroutes
    scheduleEvent(2500, () => {
      addEvent(mkEvent('NAVIGATOR', 'Computing Pareto-optimal alternative routes for 3 affected shipments...', 'info'))
    })

    // T+3200ms: Show first reroute with Pareto panel
    scheduleEvent(3200, () => {
      addEvent(mkEvent('NAVIGATOR', 'SHP-002 rerouted: Shanghai → Singapore → Rotterdam → Frankfurt DC. Saved 12h potential delay. Carbon: 533kg (vs 4,430kg air alternative)', 'info'))
      setActiveReroute(HAMBURG_REROUTES[0])
      setShipments(prev => prev.map(s =>
        s.shipment_id === 'SHP-002' ? { ...s, route_planned: ['shanghai_port','singapore_port','rotterdam_port','frankfurt_dc'], destination: 'frankfurt_dc' } : s
      ))
      setMetrics(m => ({ ...m, reroutes: 1 }))
    })

    // T+4500ms: More reroutes
    scheduleEvent(4500, () => {
      addEvent(mkEvent('NAVIGATOR', 'SHP-014 rerouted via Rotterdam direct to New York DC. SLA protected.', 'info'))
      addEvent(mkEvent('NAVIGATOR', 'SHP-029 rerouted via Rotterdam rail to Paris DC. Lowest carbon option selected.', 'info'))
      setMetrics(m => ({ ...m, reroutes: 3 }))
    })

    // T+5500ms: STOCKPILE pre-positions
    scheduleEvent(5500, () => {
      addEvent(mkEvent('STOCKPILE', 'Pre-positioning 2,400 units: Rotterdam DC → Frankfurt DC. Stockout probability: 78% → 12%', 'warn'))
      addEvent(mkEvent('STOCKPILE', 'Safety stock increased at Paris DC to absorb Hamburg overflow', 'info'))
    })

    // T+6500ms: BROKER flags carrier
    scheduleEvent(6500, () => {
      addEvent(mkEvent('BROKER', 'Carrier hapag_lloyd health dropped: OTP -18% in 24h. Soft blackout flag raised.', 'warn'))
    })

    // T+7500ms: HERALD communicates
    scheduleEvent(7500, () => {
      addEvent(mkEvent('HERALD', 'Priority alert sent to CUST-DE-003 (platinum tier) — revised ETA +18h for SHP-002', 'info'))
      addEvent(mkEvent('HERALD', 'Executive risk briefing queued. 3 shipments rerouted, 0 SLA breaches projected.', 'info'))
    })
  }, [disruptionActive, addEvent, updateNode, scheduleEvent])

  // ── Shanghai Congestion scenario ──
  const injectShanghaiClosure = useCallback(() => {
    if (disruptionActive) return
    setDisruptionActive(true)

    addEvent(mkEvent('SENTINEL', 'Massive port congestion at Shanghai — throughput down 65%. Queue depth 3.5x normal.', 'critical'))
    updateNode('shanghai_port', { congestion_score: 0.92, health_score: 0.35, current_queue_depth: 42 })

    scheduleEvent(1200, () => {
      addEvent(mkEvent('SENTINEL', '6 shipments originating from Shanghai at risk. Cascade warning issued to GUARDIAN.', 'critical'))
      setMetrics(m => ({ ...m, atRisk: 6 }))
    })

    scheduleEvent(2200, () => {
      addEvent(mkEvent('GUARDIAN', 'Circuit HALF-OPEN on shanghai_port. Monitoring recovery. Probe interval: 4h.', 'warn'))
      updateNode('shanghai_port', { circuit_state: 'half_open', health_score: 0.31 })
    })

    scheduleEvent(3500, () => {
      addEvent(mkEvent('NAVIGATOR', 'SHP-004, SHP-008, SHP-016 staging at upstream nodes. Monitoring 24h window.', 'info'))
      addEvent(mkEvent('STOCKPILE', 'Pre-positioning inventory from Tokyo Hub and Seoul Hub to buffer demand.', 'info'))
      setMetrics(m => ({ ...m, reroutes: 2 }))
    })

    scheduleEvent(5000, () => {
      addEvent(mkEvent('HERALD', 'Digest alert sent to 4 affected customers. Next update in 4h.', 'info'))
    })
  }, [disruptionActive, addEvent, updateNode, scheduleEvent])

  // ── Red Sea Geopolitical scenario ──
  const injectRedSea = useCallback(() => {
    if (disruptionActive) return
    setDisruptionActive(true)

    addEvent(mkEvent('SENTINEL', 'Geopolitical risk spike on Dubai→Rotterdam lane. Risk: 0.28 → 0.85. Red Sea corridor compromised.', 'critical'))

    scheduleEvent(1000, () => {
      addEvent(mkEvent('GUARDIAN', 'Lane dubai_hub→rotterdam_port flagged HIGH RISK. Not circuit-breaking — alternate lanes exist.', 'warn'))
    })

    scheduleEvent(2500, () => {
      addEvent(mkEvent('NAVIGATOR', 'Rerouting 2 shipments from Suez corridor to Cape of Good Hope route. Transit +96h but risk -62%.', 'info'))
      addEvent(mkEvent('NAVIGATOR', 'Green-Resilience analysis: Cape route is 18% lower carbon than air freight alternative.', 'info'))
      setMetrics(m => ({ ...m, atRisk: 2, reroutes: 2 }))
    })

    scheduleEvent(4000, () => {
      addEvent(mkEvent('BROKER', 'Carrier capacity on alternate lanes: MSC has 340 TEU available. Booking recommended.', 'info'))
      addEvent(mkEvent('HERALD', 'Stakeholder update: Red Sea disruption, 2 shipments rerouted, no SLA impact projected.', 'info'))
    })
  }, [disruptionActive, addEvent, updateNode, scheduleEvent])

  // ── Reset ──
  const resetSimulation = useCallback(() => {
    timers.current.forEach(clearTimeout)
    timers.current = []
    setNodes(structuredClone(INITIAL_NODES))
    setShipments(structuredClone(INITIAL_SHIPMENTS))
    setEvents([])
    setSelectedNode(null)
    setActiveReroute(null)
    setMetrics({ totalShipments: 12, atRisk: 0, circuitOpens: 0, reroutes: 0, delivered: 0 })
    setDisruptionActive(false)
    _evtId = 0
  }, [])

  const dismissReroute = useCallback(() => setActiveReroute(null), [])

  return {
    nodes, edges, shipments, events, metrics, selectedNode, activeReroute, disruptionActive,
    setSelectedNode, dismissReroute,
    injectHamburgStorm, injectShanghaiClosure, injectRedSea, resetSimulation,
  }
}
