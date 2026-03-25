import React, { useMemo, useState, useRef, useCallback } from 'react'

const NODE_POSITIONS = {
    SE: { x: 100, y: 100, label: 'Seattle' },
    SV: { x: 100, y: 300, label: 'Sunnyvale' },
    LA: { x: 180, y: 460, label: 'Los Angeles' },
    DE: { x: 320, y: 160, label: 'Denver' },
    KC: { x: 460, y: 260, label: 'Kansas City' },
    HO: { x: 400, y: 440, label: 'Houston' },
    IN: { x: 580, y: 200, label: 'Indianapolis' },
    AT: { x: 600, y: 400, label: 'Atlanta' },
    CH: { x: 560, y: 80, label: 'Chicago' },
    WA: { x: 720, y: 280, label: 'Washington' },
    NY: { x: 780, y: 120, label: 'New York' },
}

function puColor(pu) {
    if (pu >= 70) return '#ff006e'
    if (pu >= 50) return '#ffaa00'
    if (pu >= 30) return '#00d4ff'
    return '#00ff88'
}

function nodeColor(pu) {
    // Average PU of connected links — passed as prop
    if (pu >= 60) return '#ff006e'
    if (pu >= 40) return '#ffaa00'
    return '#00d4ff'
}

export default function TopologyView({ topology }) {
    const [tooltip, setTooltip] = useState(null)
    const [scale, setScale] = useState(1)
    const [translate, setTranslate] = useState({ x: 0, y: 0 })
    const [isPanning, setIsPanning] = useState(false)
    const panStart = useRef({ x: 0, y: 0 })
    const svgRef = useRef(null)

    const { links, activePath } = useMemo(() => {
        if (!topology) return { links: [], activePath: [] }
        return {
            links: topology.links || [],
            activePath: topology.active_path || [],
        }
    }, [topology])

    const handleWheel = useCallback((e) => {
        e.preventDefault()
        const delta = e.deltaY > 0 ? -0.1 : 0.1
        setScale(prev => Math.min(Math.max(prev + delta, 0.4), 3))
    }, [])

    const handleMouseDown = useCallback((e) => {
        if (e.target.closest('.topo-node')) return
        setIsPanning(true)
        panStart.current = { x: e.clientX - translate.x, y: e.clientY - translate.y }
    }, [translate])

    const handleMouseMove = useCallback((e) => {
        if (!isPanning) return
        const svg = svgRef.current
        if (!svg) return
        const rect = svg.getBoundingClientRect()
        const dx = (e.clientX - panStart.current.x) / rect.width * 900
        const dy = (e.clientY - panStart.current.y) / rect.height * 600
        setTranslate({ x: dx, y: dy })
    }, [isPanning])

    const handleMouseUp = useCallback(() => setIsPanning(false), [])

    const resetView = useCallback(() => {
        setScale(1)
        setTranslate({ x: 0, y: 0 })
    }, [])

    // Build active path edge set
    const activeEdges = useMemo(() => {
        const edges = new Set()
        for (let i = 0; i < activePath.length - 1; i++) {
            const a = activePath[i], b = activePath[i + 1]
            edges.add(`${a}-${b}`)
            edges.add(`${b}-${a}`)
        }
        return edges
    }, [activePath])

    const handleNodeEnter = (e, nodeId) => {
        const rect = e.currentTarget.closest('svg').getBoundingClientRect()
        const x = e.clientX - rect.left + 15
        const y = e.clientY - rect.top - 10
        const pos = NODE_POSITIONS[nodeId]

        // Find connected links
        const connectedLinks = links.filter(l => l.source === nodeId || l.target === nodeId)
        const avgPu = connectedLinks.length > 0
            ? connectedLinks.reduce((s, l) => s + l.pu_forward, 0) / connectedLinks.length
            : 0

        setTooltip({
            x, y,
            nodeId,
            label: pos?.label || nodeId,
            avgPu: avgPu.toFixed(1),
            links: connectedLinks.length,
        })
    }

    const handleLinkEnter = (e, link) => {
        const rect = e.currentTarget.closest('svg').getBoundingClientRect()
        setTooltip({
            x: e.clientX - rect.left + 15,
            y: e.clientY - rect.top - 10,
            isLink: true,
            link,
        })
    }

    if (!topology) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                Connecting to simulation...
            </div>
        )
    }

    return (
        <div className="topology-svg" style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10, display: 'flex', gap: 4 }}>
                <button className="topo-ctrl-btn" onClick={() => setScale(s => Math.min(s + 0.2, 3))} title="Zoom In">＋</button>
                <button className="topo-ctrl-btn" onClick={() => setScale(s => Math.max(s - 0.2, 0.4))} title="Zoom Out">−</button>
                <button className="topo-ctrl-btn" onClick={resetView} title="Reset View">⟲</button>
            </div>

            {/* Topology Legend */}
            <div style={{
                position: 'absolute', bottom: 8, left: 8, zIndex: 10,
                background: 'rgba(6,8,26,0.92)', backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8,
                padding: '8px 12px', fontSize: 10, lineHeight: 1.8,
            }}>
                <div style={{ fontWeight: 700, fontSize: 10, color: 'var(--text-secondary)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: 0.5 }}>Legend</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 20, height: 3, background: '#ff006e', borderRadius: 2 }} />
                    <span style={{ color: '#ff006e' }}>Congested link (PU ≥ 70%)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 20, height: 3, background: '#00d4ff', borderRadius: 2, borderTop: '1px dashed #00d4ff' }} />
                    <span style={{ color: '#00d4ff' }}>Alternate path being evaluated</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 20, height: 3, background: '#00ff88', borderRadius: 2 }} />
                    <span style={{ color: '#00ff88' }}>Healthy link (PU &lt; 30%)</span>
                </div>
                {activePath.length > 1 && (
                    <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Current route: </span>
                        <span style={{ color: 'var(--amber)' }}>{activePath.join(' → ')}</span>
                    </div>
                )}
            </div>

            <svg
                ref={svgRef}
                viewBox="0 0 900 560"
                preserveAspectRatio="xMidYMid meet"
                style={{ width: '100%', height: '100%', cursor: isPanning ? 'grabbing' : 'grab' }}
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
            >
                <defs>
                    <filter id="glow">
                        <feGaussianBlur stdDeviation="4" result="coloredBlur" />
                        <feMerge>
                            <feMergeNode in="coloredBlur" />
                            <feMergeNode in="SourceGraphic" />
                        </feMerge>
                    </filter>
                    <filter id="nodeGlow">
                        <feGaussianBlur stdDeviation="6" result="coloredBlur" />
                        <feMerge>
                            <feMergeNode in="coloredBlur" />
                            <feMergeNode in="SourceGraphic" />
                        </feMerge>
                    </filter>
                    <radialGradient id="nodeGrad" cx="40%" cy="40%">
                        <stop offset="0%" stopColor="rgba(255,255,255,0.15)" />
                        <stop offset="100%" stopColor="rgba(255,255,255,0)" />
                    </radialGradient>
                </defs>

                <g transform={`translate(${translate.x}, ${translate.y}) scale(${scale})`}>
                    {/* Links */}
                    {links.map((link, i) => {
                        const src = NODE_POSITIONS[link.source]
                        const tgt = NODE_POSITIONS[link.target]
                        if (!src || !tgt) return null

                        const isActive = activeEdges.has(`${link.source}-${link.target}`)
                        const isBn = link.is_bottleneck
                        const color = isBn ? '#ff006e' : (isActive ? '#00d4ff' : puColor(link.pu_forward))
                        const width = isBn ? 3.5 : (isActive ? 2.5 : 1.5)

                        return (
                            <g key={`link-${i}`}>
                                {/* Glow for bottleneck or active */}
                                {(isBn || isActive) && (
                                    <line
                                        x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                                        stroke={color} strokeWidth={width + 4}
                                        strokeOpacity={0.15} strokeLinecap="round"
                                    />
                                )}
                                <line
                                    x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                                    stroke={color} strokeWidth={width}
                                    strokeOpacity={isBn ? 0.9 : (isActive ? 0.8 : 0.35)}
                                    strokeLinecap="round"
                                    className={`topo-link-line ${isBn ? 'bottleneck' : ''} ${isActive ? 'active-path' : ''}`}
                                    onMouseEnter={e => handleLinkEnter(e, link)}
                                    onMouseLeave={() => setTooltip(null)}
                                    style={{ cursor: 'pointer' }}
                                />
                                {/* PU label on link */}
                                <text
                                    x={(src.x + tgt.x) / 2}
                                    y={(src.y + tgt.y) / 2 - 6}
                                    textAnchor="middle"
                                    fill={isBn ? '#ff006e' : 'rgba(255,255,255,0.3)'}
                                    fontSize={isBn ? 10 : 8}
                                    fontWeight={isBn ? 700 : 400}
                                    style={{ pointerEvents: 'none' }}
                                >
                                    {link.pu_forward}%
                                </text>
                            </g>
                        )
                    })}

                    {/* Nodes */}
                    {Object.entries(NODE_POSITIONS).map(([nodeId, pos]) => {
                        const connLinks = links.filter(l => l.source === nodeId || l.target === nodeId)
                        const avgPu = connLinks.length > 0
                            ? connLinks.reduce((s, l) => s + l.pu_forward, 0) / connLinks.length
                            : 0
                        const hasBottleneck = connLinks.some(l => l.is_bottleneck)
                        const isInPath = activePath.includes(nodeId)
                        const color = hasBottleneck ? '#ff006e' : (isInPath ? '#00d4ff' : nodeColor(avgPu))
                        const r = 18

                        return (
                            <g key={nodeId} className="topo-node"
                                onMouseEnter={e => handleNodeEnter(e, nodeId)}
                                onMouseLeave={() => setTooltip(null)}
                                style={{ cursor: 'pointer' }}
                            >
                                {/* Outer glow */}
                                {(hasBottleneck || isInPath) && (
                                    <circle cx={pos.x} cy={pos.y} r={r + 8}
                                        fill="none" stroke={color} strokeWidth={2}
                                        strokeOpacity={0.2}
                                        strokeDasharray={hasBottleneck ? '4 3' : 'none'}
                                        className={hasBottleneck ? 'pulse' : ''}
                                    />
                                )}
                                {/* Main circle */}
                                <circle cx={pos.x} cy={pos.y} r={r}
                                    fill={`${color}30`}
                                    stroke={color} strokeWidth={2} strokeOpacity={0.7}
                                />
                                {/* Inner highlight */}
                                <circle cx={pos.x} cy={pos.y} r={r}
                                    fill="url(#nodeGrad)"
                                />
                                {/* Node ID */}
                                <text x={pos.x} y={pos.y + 1}
                                    textAnchor="middle" dominantBaseline="central"
                                    fill="white" fontSize={12} fontWeight={700}
                                    style={{ pointerEvents: 'none' }}
                                >
                                    {nodeId}
                                </text>
                                {/* Label below */}
                                <text x={pos.x} y={pos.y + r + 14}
                                    textAnchor="middle"
                                    fill="rgba(255,255,255,0.4)" fontSize={9}
                                    style={{ pointerEvents: 'none' }}
                                >
                                    {pos.label}
                                </text>
                            </g>
                        )
                    })}
                </g>
            </svg>

            {/* Tooltip */}
            {tooltip && (
                <div className="tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
                    {tooltip.isLink ? (
                        <>
                            <div className="tooltip-title">{tooltip.link.source} → {tooltip.link.target}</div>
                            <div className="tooltip-row"><span>Port Util</span><span>{tooltip.link.pu_forward}%</span></div>
                            <div className="tooltip-row"><span>Avail BW</span><span>{tooltip.link.avail_forward} Mbps</span></div>
                            <div className="tooltip-row"><span>Status</span>
                                <span style={{ color: tooltip.link.is_bottleneck ? '#ff006e' : '#00ff88' }}>
                                    {tooltip.link.is_bottleneck ? '⚠ Bottleneck' : '✓ Normal'}
                                </span>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="tooltip-title">{tooltip.label} ({tooltip.nodeId})</div>
                            <div className="tooltip-row"><span>Avg PU</span><span>{tooltip.avgPu}%</span></div>
                            <div className="tooltip-row"><span>Links</span><span>{tooltip.links}</span></div>
                        </>
                    )}
                </div>
            )}
        </div>
    )
}
