import { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import {
  XAxis,
  YAxis,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts'
import { RotateCcw, TrendingUp, Crosshair, RefreshCw } from 'lucide-react'
import RLLayout from '@/components/layout/RLLayout'
import { cn } from '@/lib/utils'

/* ═══════════════════════════════════════════════════════════════
   GRAPH NODE DATA
   ═══════════════════════════════════════════════════════════════ */
interface GraphNode {
  id: string
  label: string
  x: number
  y: number
  shape: 'circle' | 'square'
  radius: number
  color: number
  isBottleneck?: boolean
}

const GRAPH_NODES: GraphNode[] = [
  { id: 'hub-amer',       label: 'HUB_AMER_N',        x: -3,  y: 2,    shape: 'circle', radius: 0.3,  color: 0x00ff41 },
  { id: 'hub-apac',       label: 'HUB_APAC_N',        x: 3,   y: 2,    shape: 'circle', radius: 0.3,  color: 0x00ff41 },
  { id: 'core-emea',      label: 'CORE_EMEA',          x: 0.5, y: 0,    shape: 'square', radius: 0.25, color: 0x00ff41 },
  { id: 'bottleneck',     label: 'BOTTLENECK_LATAM',   x: -1,  y: -1,   shape: 'circle', radius: 0.3,  color: 0xff4466, isBottleneck: true },
  { id: 'unnamed',        label: '',                    x: 3,   y: -0.5, shape: 'circle', radius: 0.15, color: 0x00ff41 },
]

interface GraphEdge {
  from: string
  to: string
  dashed: boolean
  faint?: boolean
}

const GRAPH_EDGES: GraphEdge[] = [
  { from: 'hub-amer',   to: 'hub-apac',   dashed: false },
  { from: 'hub-apac',   to: 'core-emea',  dashed: false },
  { from: 'core-emea',  to: 'bottleneck', dashed: true },
  { from: 'hub-amer',   to: 'bottleneck', dashed: true },
  { from: 'bottleneck', to: 'unnamed',    dashed: false, faint: true },
]

/* ═══════════════════════════════════════════════════════════════
   ACTION LOG DATA
   ═══════════════════════════════════════════════════════════════ */
interface ActionEntry {
  ts: string
  reward: number
  title: string
  detail: string
}

const ACTION_LOG: ActionEntry[] = [
  { ts: '14:02:11.094', reward: 5.2,  title: 'Rerouted SHP-9921-A to Avoid Delay',       detail: '↳ NODE_LATAM → HUB_AMER_N' },
  { ts: '14:02:09.551', reward: 1.8,  title: 'Increased Stock Level',                     detail: '↳ TARGET: HUB_ALPHA (SKU-882)' },
  { ts: '14:01:55.220', reward: -1.0, title: 'Capacity Exceeded Action Denied',            detail: '↳ EXPEDITE_SHP on BOTTLENECK_LATAM' },
  { ts: '14:01:40.102', reward: 0.5,  title: 'Maintained Holding Pattern',                 detail: '↳ FLEET_04 at IDLE_STATION' },
  { ts: '14:01:22.881', reward: 0.0,  title: 'Random Exploration Action',                  detail: '↳ ε-GREEDY TRIGGERED' },
]

/* ═══════════════════════════════════════════════════════════════
   EXPLORATION RATE CHART DATA (exponential decay)
   ═══════════════════════════════════════════════════════════════ */
const EXPLORATION_DATA = Array.from({ length: 50 }, (_, i) => ({
  ep: i === 0 ? 'EP_0' : i === 49 ? 'EP_CURRENT' : '',
  rate: 1.0 * Math.exp(-0.06 * i),
}))

/* ═══════════════════════════════════════════════════════════════
   POLICY BARS
   ═══════════════════════════════════════════════════════════════ */
const POLICY_BARS = [
  { label: 'REROUTE_NODE',   pct: 45, active: true },
  { label: 'HOLD_INVENTORY', pct: 30, active: false },
  { label: 'EXPEDITE_SHP',   pct: 25, active: false },
]

/* ═══════════════════════════════════════════════════════════════
   COUNT-UP HOOK
   ═══════════════════════════════════════════════════════════════ */
function useCountUp(target: number, duration = 1400) {
  const [val, setVal] = useState(0)
  const raf = useRef(0)

  useEffect(() => {
    let start: number | null = null
    const step = (ts: number) => {
      if (!start) start = ts
      const p = Math.min((ts - start) / duration, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      setVal(eased * target)
      if (p < 1) raf.current = requestAnimationFrame(step)
      else setVal(target)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [target, duration])

  return val
}

/* ═══════════════════════════════════════════════════════════════
   THREE.JS NODE GRAPH COMPONENT
   ═══════════════════════════════════════════════════════════════ */
function NodeGraph() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const [fps, setFps] = useState(0)

  const initThree = useCallback(() => {
    const canvas = canvasRef.current
    const overlay = overlayRef.current
    if (!canvas || !overlay) return

    const width = canvas.clientWidth
    const height = canvas.clientHeight
    const aspect = width / height

    // ── Renderer ──
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
    })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(0x0a0a0a)

    // ── Camera (orthographic, 2D view) ──
    const frustum = 5
    const camera = new THREE.OrthographicCamera(
      -frustum * aspect,
       frustum * aspect,
       frustum,
      -frustum,
      0.1,
      100
    )
    camera.position.set(0, 0, 10)
    camera.lookAt(0, 0, 0)

    // ── Scene ──
    const scene = new THREE.Scene()

    // ── Create node meshes ──
    const meshes: { node: GraphNode; mesh: THREE.Mesh }[] = []

    for (const node of GRAPH_NODES) {
      const geo =
        node.shape === 'square'
          ? new THREE.PlaneGeometry(node.radius * 2, node.radius * 2)
          : new THREE.CircleGeometry(node.radius, 32)
      const mat = new THREE.MeshBasicMaterial({ color: node.color })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.position.set(node.x, node.y, 0)
      scene.add(mesh)
      meshes.push({ node, mesh })
    }

    // ── Create edges ──
    const nodePosMap = new Map(
      GRAPH_NODES.map((n) => [n.id, new THREE.Vector3(n.x, n.y, 0)])
    )

    for (const edge of GRAPH_EDGES) {
      const fromPos = nodePosMap.get(edge.from)!
      const toPos = nodePosMap.get(edge.to)!

      if (edge.dashed) {
        // Dashed: create points with gaps
        const points: THREE.Vector3[] = []
        const segLen = 0.15
        const gapLen = 0.1
        const dir = toPos.clone().sub(fromPos)
        const totalLen = dir.length()
        dir.normalize()
        let d = 0
        let drawing = true
        while (d < totalLen) {
          const step = drawing ? segLen : gapLen
          const end = Math.min(d + step, totalLen)
          if (drawing) {
            points.push(fromPos.clone().add(dir.clone().multiplyScalar(d)))
            points.push(fromPos.clone().add(dir.clone().multiplyScalar(end)))
          }
          d = end
          drawing = !drawing
        }
        const geo = new THREE.BufferGeometry().setFromPoints(points)
        const mat = new THREE.LineBasicMaterial({
          color: edge.faint ? 0x00ff41 : 0x00ff41,
          opacity: edge.faint ? 0.15 : 0.35,
          transparent: true,
        })
        const line = new THREE.LineSegments(geo, mat)
        scene.add(line)
      } else {
        const geo = new THREE.BufferGeometry().setFromPoints([fromPos, toPos])
        const mat = new THREE.LineBasicMaterial({
          color: 0x00ff41,
          opacity: edge.faint ? 0.15 : 0.5,
          transparent: true,
        })
        const line = new THREE.Line(geo, mat)
        scene.add(line)
      }
    }

    // ── Animation loop ──
    const clock = new THREE.Clock()
    let frameCount = 0
    let lastFpsTime = 0
    let currentAnimId = 0

    const animate = () => {
      const t = clock.getElapsedTime()

      // Pulse nodes
      for (const { node, mesh } of meshes) {
        const s = 1 + 0.1 * Math.sin(t * 2 + mesh.position.x)
        mesh.scale.set(s, s, 1)

        // Bottleneck red glow cycle
        if (node.isBottleneck) {
          const r = 0.5 + 0.5 * Math.sin(t * 3)
          ;(mesh.material as THREE.MeshBasicMaterial).color.setRGB(
            1,
            0.1 + 0.17 * r,
            0.2 + 0.2 * r
          )
        }
      }

      // Sync HTML labels to 3D positions
      for (const { node, mesh } of meshes) {
        if (!node.label) continue
        const el = overlay.querySelector(`[data-node="${node.id}"]`) as HTMLElement | null
        if (!el) continue

        const vec = mesh.position.clone().project(camera)
        const x = (vec.x * 0.5 + 0.5) * width
        const y = (-vec.y * 0.5 + 0.5) * height
        el.style.transform = `translate(${x}px, ${y + 18}px)`
      }

      renderer.render(scene, camera)

      // FPS counter
      frameCount++
      if (t - lastFpsTime >= 1) {
        setFps(frameCount)
        frameCount = 0
        lastFpsTime = t
      }

      currentAnimId = requestAnimationFrame(animate)
    }

    currentAnimId = requestAnimationFrame(animate)

    // ── Resize handler ──
    const onResize = () => {
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (w === 0 || h === 0) return
      const a = w / h
      camera.left = -frustum * a
      camera.right = frustum * a
      camera.top = frustum
      camera.bottom = -frustum
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }

    const observer = new ResizeObserver(onResize)
    observer.observe(canvas)

    return () => {
      cancelAnimationFrame(currentAnimId)
      observer.disconnect()
      renderer.dispose()
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose()
          ;(obj.material as THREE.Material).dispose()
        }
        if (obj instanceof THREE.Line || obj instanceof THREE.LineSegments) {
          obj.geometry.dispose()
          ;(obj.material as THREE.Material).dispose()
        }
      })
    }
  }, [])

  useEffect(() => {
    const cleanup = initThree()
    return () => cleanup?.()
  }, [initThree])

  return (
    <div className="relative w-full h-full">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />

      {/* HTML label overlay */}
      <div ref={overlayRef} className="pointer-events-none absolute inset-0 overflow-hidden">
        {GRAPH_NODES.filter((n) => n.label).map((node) => (
          <div
            key={node.id}
            data-node={node.id}
            className={cn(
              'absolute left-0 top-0 -translate-x-1/2 whitespace-nowrap rounded-sm px-2 py-0.5 text-[9px] font-bold tracking-widest',
              node.isBottleneck
                ? 'border border-critical/50 bg-critical/20 text-critical'
                : 'bg-bg/80 text-text/80'
            )}
          >
            {node.label}
          </div>
        ))}
      </div>

      {/* Bottom bar: STEP + FPS */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2">
        <div className="flex items-center gap-1.5 rounded-sm border border-neon/50 bg-bg/80 px-3 py-1">
          <RefreshCw size={10} className="text-neon" />
          <span className="text-[10px] font-bold tracking-widest text-neon">
            STEP: 1,402,991
          </span>
        </div>
        <div className="flex items-center gap-1.5 rounded-sm border border-border bg-bg/80 px-3 py-1">
          <span className="text-[10px] font-bold tracking-widest text-muted">
            ⊙ FPS: {fps || '—'}
          </span>
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════
   RWD BADGE
   ═══════════════════════════════════════════════════════════════ */
function RewardBadge({ value }: { value: number }) {
  const sign = value > 0 ? '+' : value < 0 ? '' : ''
  const label = `${sign}${value.toFixed(1)} RWD`
  return (
    <span
      className={cn(
        'shrink-0 rounded-sm px-2 py-0.5 text-[9px] font-bold tracking-wider',
        value > 0 && 'bg-neon/15 text-neon',
        value < 0 && 'bg-critical/15 text-critical',
        value === 0 && 'bg-border/30 text-muted'
      )}
    >
      {label}
    </span>
  )
}

/* ═══════════════════════════════════════════════════════════════
   PAGE COMPONENT
   ═══════════════════════════════════════════════════════════════ */
export default function RLOptimizerPage() {
  const cumulativeReward = useCountUp(4291.55)
  const [barsVisible, setBarsVisible] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setBarsVisible(true), 400)
    return () => clearTimeout(t)
  }, [])

  return (
    <RLLayout>
      <div className="flex flex-col h-full -m-6">
        {/* ─── Top section: graph + action log ─── */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* LEFT: graph area */}
          <div className="flex-1 flex flex-col min-w-0 border-r border-border">
            {/* Header */}
            <div className="flex items-center gap-2 px-5 pt-4 pb-3">
              <svg width="10" height="10" viewBox="0 0 10 10" className="shrink-0">
                <circle cx="5" cy="5" r="4" fill="oklch(85% 0.35 142)" />
              </svg>
              <h2 className="font-display text-lg font-bold tracking-wider text-text">
                GLOBAL_STATE_VIEW
              </h2>
            </div>

            {/* Three.js canvas */}
            <div className="flex-1 min-h-0 relative">
              <NodeGraph />
            </div>

            {/* Green progress bar under graph */}
            <div className="h-1 w-full bg-neon/30">
              <div className="h-full w-2/3 bg-neon animate-bar-fill" />
            </div>
          </div>

          {/* RIGHT: Action log sidebar */}
          <div className="w-[320px] shrink-0 flex flex-col bg-bg">
            {/* Header */}
            <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <Crosshair size={14} className="text-neon" />
                <h3 className="text-[11px] font-semibold tracking-[0.15em] uppercase text-text">
                  Action Log
                </h3>
              </div>
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-pulse-glow rounded-full bg-neon" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-neon" />
              </span>
            </div>

            {/* Log entries with vertical fade */}
            <div
              className="flex-1 overflow-y-auto px-4"
              style={{
                maskImage: 'linear-gradient(to bottom, transparent, black 10%, black 90%, transparent)',
                WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 10%, black 90%, transparent)',
              }}
            >
              {ACTION_LOG.map((entry, i) => (
                <div
                  key={i}
                  className="border-b border-border py-3 animate-slide-in-right opacity-0"
                  style={{
                    animationDelay: `${i * 100}ms`,
                    animationFillMode: 'forwards',
                  }}
                >
                  {/* Top row: timestamp + badge */}
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] tracking-widest text-muted">
                      TS: {entry.ts}
                    </span>
                    <RewardBadge value={entry.reward} />
                  </div>
                  {/* Title */}
                  <p className="text-[12px] font-bold text-text mb-0.5">
                    {entry.title}
                  </p>
                  {/* Detail */}
                  <p className="text-[10px] tracking-widest text-muted">
                    {entry.detail}
                  </p>
                </div>
              ))}
            </div>

            {/* Bottom button */}
            <div className="p-4 border-t border-border">
              <button
                id="btn-reward-reboot"
                className="flex w-full items-center justify-center gap-2 rounded-sm border border-neon bg-neon/5 px-4 py-2.5 text-[11px] font-bold tracking-widest text-neon transition-colors hover:bg-neon/10"
              >
                <RotateCcw size={14} />
                REWARD_REBOOT
              </button>
            </div>
          </div>
        </div>

        {/* ─── Bottom 3 metric cards ─── */}
        <div className="grid grid-cols-3 gap-0 border-t border-border shrink-0">
          {/* Card 1: Agent Performance */}
          <div className="border-r border-border p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[11px] font-semibold tracking-[0.15em] uppercase text-muted">
                Agent Performance
              </h3>
              <TrendingUp size={14} className="text-muted" />
            </div>
            <p className="text-[9px] tracking-[0.2em] uppercase text-muted mb-1">
              CUMULATIVE_REWARD
            </p>
            <p className="font-display text-3xl font-bold text-neon leading-none">
              +{cumulativeReward.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </p>
            <p className="mt-1.5 text-[10px] tracking-widest text-neon-dim">
              ↑ 12.4% vs prev episode
            </p>
          </div>

          {/* Card 2: Policy Distribution */}
          <div className="border-r border-border p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[11px] font-semibold tracking-[0.15em] uppercase text-muted">
                Policy Distribution
              </h3>
              <Crosshair size={14} className="text-muted" />
            </div>
            <div className="space-y-2.5">
              {POLICY_BARS.map((bar) => (
                <div key={bar.label} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold tracking-widest text-text">
                      {bar.label}
                    </span>
                    <span className="text-[10px] text-muted">{bar.pct}%</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/30">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all duration-1000 ease-out',
                        bar.active ? 'bg-neon' : 'bg-neon-dim/40'
                      )}
                      style={{ width: barsVisible ? `${bar.pct}%` : '0%' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Card 3: Exploration Rate */}
          <div className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[11px] font-semibold tracking-[0.15em] uppercase text-muted">
                Exploration Rate
              </h3>
              <Crosshair size={14} className="text-muted" />
            </div>
            <p className="font-display text-lg font-bold text-text mb-2">
              ε = 0.05
            </p>
            <div className="h-[70px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={EXPLORATION_DATA}
                  margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
                >
                  <defs>
                    <linearGradient id="neonFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="oklch(85% 0.35 142)" stopOpacity={0.15} />
                      <stop offset="100%" stopColor="oklch(85% 0.35 142)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="ep"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 8, fill: 'oklch(55% 0.02 142)' }}
                    interval="preserveStartEnd"
                  />
                  <YAxis hide />
                  <Area
                    type="monotone"
                    dataKey="rate"
                    stroke="oklch(85% 0.35 142)"
                    strokeWidth={1.5}
                    fill="url(#neonFill)"
                    dot={false}
                    animationDuration={1500}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </RLLayout>
  )
}
