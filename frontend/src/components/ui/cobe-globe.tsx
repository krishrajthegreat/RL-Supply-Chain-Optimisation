import { useEffect, useRef, useCallback } from "react"
import createGlobe from "cobe"

interface Marker {
  id: string
  location: [number, number]
  label: string
}

interface Arc {
  id: string
  from: [number, number]
  to: [number, number]
  label?: string
}

interface GlobeProps {
  markers?: Marker[]
  arcs?: Arc[]
  className?: string
  markerColor?: [number, number, number]
  baseColor?: [number, number, number]
  arcColor?: [number, number, number]
  glowColor?: [number, number, number]
  dark?: number
  mapBrightness?: number
  markerSize?: number
  markerElevation?: number
  arcWidth?: number
  arcHeight?: number
  speed?: number
  theta?: number
  diffuse?: number
  mapSamples?: number
}

export function Globe({
  markers = [],
  arcs = [],
  className = "",
  markerColor = [0.37, 0.82, 0.61],
  baseColor = [0.04, 0.07, 0.05],
  arcColor = [0.37, 0.82, 0.61],
  glowColor = [0.12, 0.3, 0.2],
  dark = 1,
  mapBrightness = 6,
  markerSize = 0.03,
  markerElevation = 0.01,
  arcWidth = 0.8,
  arcHeight = 0.32,
  speed = 0.002,
  theta = 0.25,
  diffuse = 1.1,
  mapSamples = 16000,
}: GlobeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const pointerInteracting = useRef<{ x: number; y: number } | null>(null)
  const lastPointer    = useRef<{ x: number; y: number; t: number } | null>(null)
  const dragOffset     = useRef({ phi: 0, theta: 0 })
  const velocity       = useRef({ phi: 0, theta: 0 })
  const phiOffsetRef   = useRef(0)
  const thetaOffsetRef = useRef(0)
  const isPausedRef    = useRef(false)

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    pointerInteracting.current = { x: e.clientX, y: e.clientY }
    if (canvasRef.current) canvasRef.current.style.cursor = "grabbing"
    isPausedRef.current = true
  }, [])

  const handlePointerMove = useCallback((e: PointerEvent) => {
    if (pointerInteracting.current !== null) {
      const dx = e.clientX - pointerInteracting.current.x
      const dy = e.clientY - pointerInteracting.current.y
      dragOffset.current = { phi: dx / 300, theta: dy / 1000 }
      const now = Date.now()
      if (lastPointer.current) {
        const dt = Math.max(now - lastPointer.current.t, 1)
        const cap = 0.15
        velocity.current = {
          phi:   Math.max(-cap, Math.min(cap, ((e.clientX - lastPointer.current.x) / dt) * 0.3)),
          theta: Math.max(-cap, Math.min(cap, ((e.clientY - lastPointer.current.y) / dt) * 0.08)),
        }
      }
      lastPointer.current = { x: e.clientX, y: e.clientY, t: now }
    }
  }, [])

  const handlePointerUp = useCallback(() => {
    if (pointerInteracting.current !== null) {
      phiOffsetRef.current  += dragOffset.current.phi
      thetaOffsetRef.current += dragOffset.current.theta
      dragOffset.current = { phi: 0, theta: 0 }
      lastPointer.current = null
    }
    pointerInteracting.current = null
    if (canvasRef.current) canvasRef.current.style.cursor = "grab"
    isPausedRef.current = false
  }, [])

  useEffect(() => {
    window.addEventListener("pointermove", handlePointerMove, { passive: true })
    window.addEventListener("pointerup",   handlePointerUp,   { passive: true })
    return () => {
      window.removeEventListener("pointermove", handlePointerMove)
      window.removeEventListener("pointerup",   handlePointerUp)
    }
  }, [handlePointerMove, handlePointerUp])

  useEffect(() => {
    if (!canvasRef.current) return
    const canvas = canvasRef.current
    let globe: ReturnType<typeof createGlobe> | null = null
    let animationId: number
    let phi = 0

    function init() {
      const width = canvas.offsetWidth
      if (width === 0 || globe) return
      const dpr = Math.min(window.devicePixelRatio || 1, 2)

      globe = createGlobe(canvas, {
        devicePixelRatio: dpr,
        width,
        height: width,
        phi: 0,
        theta,
        dark,
        diffuse,
        mapSamples,
        mapBrightness,
        baseColor,
        markerColor,
        glowColor,
        markerElevation,
        markers: markers.map(m => ({ location: m.location, size: markerSize, id: m.id })),
        arcs: arcs.map(a => ({ from: a.from, to: a.to, id: a.id })),
        arcColor,
        arcWidth,
        arcHeight,
        opacity: 0.85,
      })

      function animate() {
        if (!isPausedRef.current) {
          phi += speed
          if (Math.abs(velocity.current.phi) > 0.0001 || Math.abs(velocity.current.theta) > 0.0001) {
            phiOffsetRef.current  += velocity.current.phi
            thetaOffsetRef.current += velocity.current.theta
            velocity.current.phi   *= 0.95
            velocity.current.theta *= 0.95
          }
          const tMin = -0.4, tMax = 0.4
          if (thetaOffsetRef.current < tMin) thetaOffsetRef.current += (tMin - thetaOffsetRef.current) * 0.1
          if (thetaOffsetRef.current > tMax) thetaOffsetRef.current += (tMax - thetaOffsetRef.current) * 0.1
        }

        const curPhi   = phi + phiOffsetRef.current + dragOffset.current.phi
        const curTheta = theta + thetaOffsetRef.current + dragOffset.current.theta

        globe!.update({
          phi: curPhi,
          theta: curTheta,
          dark, mapBrightness, markerColor, baseColor, arcColor, markerElevation,
          markers: markers.map(m => ({ location: m.location, size: markerSize, id: m.id })),
          arcs: arcs.map(a => ({ from: a.from, to: a.to, id: a.id })),
        })

        animationId = requestAnimationFrame(animate)
      }

      animate()
      setTimeout(() => { if (canvas) canvas.style.opacity = "1" })
    }

    if (canvas.offsetWidth > 0) {
      init()
    } else {
      const ro = new ResizeObserver(entries => {
        if (entries[0]?.contentRect.width > 0) { ro.disconnect(); init() }
      })
      ro.observe(canvas)
    }

    return () => {
      if (animationId) cancelAnimationFrame(animationId)
      if (globe) globe.destroy()
    }
  }, [markers, arcs, markerColor, baseColor, arcColor, glowColor, dark,
      mapBrightness, markerSize, markerElevation, arcWidth, arcHeight,
      speed, theta, diffuse, mapSamples])

  return (
    <div className={`relative aspect-square select-none ${className}`}>
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        style={{
          width: "100%", height: "100%",
          cursor: "grab", opacity: 0,
          transition: "opacity 1.4s ease",
          borderRadius: "50%", touchAction: "none",
        }}
      />
    </div>
  )
}
