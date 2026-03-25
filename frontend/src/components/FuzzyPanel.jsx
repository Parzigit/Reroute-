import React from 'react'

function LAGauge({ value, color }) {
    const pct = Math.max(0, Math.min(1, value))
    const angle = pct * 180
    const r = 18, cx = 22, cy = 22
    const startRad = Math.PI
    const endRad = Math.PI - (angle * Math.PI / 180)
    const startX = cx + r * Math.cos(startRad)
    const startY = cy - r * Math.sin(startRad)
    const endX = cx + r * Math.cos(endRad)
    const endY = cy - r * Math.sin(endRad)
    const largeArc = angle > 180 ? 1 : 0

    return (
        <div className="bayes-gauge">
            <svg viewBox="0 0 44 28">
                <path
                    d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
                    fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={4}
                    strokeLinecap="round"
                />
                {pct > 0.01 && (
                    <path
                        d={`M ${startX} ${startY} A ${r} ${r} 0 ${largeArc} 1 ${endX} ${endY}`}
                        fill="none" stroke={color} strokeWidth={4}
                        strokeLinecap="round" strokeOpacity={0.9}
                    />
                )}
                <text x={cx} y={cy - 2} textAnchor="middle"
                    className="bayes-gauge-text" fill={color}>
                    {(pct * 100).toFixed(0)}%
                </text>
            </svg>
        </div>
    )
}

function explainDecision(d) {
    if (d.rb <= 0) return 'Not enough bandwidth — link is full'
    const laPercent = ((d.la ?? 0) * 100).toFixed(0)
    if (d.admitted) {
        return `Link available (LA=${laPercent}% > 50%)`
    }
    return `Link too congested (LA=${laPercent}% < 50%)`
}

export default function FuzzyPanel({ decisions }) {
    if (!decisions || decisions.length === 0) {
        return (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 16, textAlign: 'center' }}>
                <div style={{ marginBottom: 6 }}>No flow evaluation yet</div>
                <div style={{ fontSize: 11 }}>Inject a flow or wait for congestion to trigger rerouting</div>
            </div>
        )
    }

    const admitted = decisions.filter(d => d.admitted).length
    const total = decisions.length
    const allPass = admitted === total
    const blockedLinks = decisions.filter(d => !d.admitted).map(d => d.link)

    return (
        <div>
            {/* Explanation banner */}
            <div style={{
                fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5,
                padding: '6px 10px', marginBottom: 8,
                background: 'rgba(255,255,255,0.02)', borderRadius: 6,
            }}>
                Evaluating each link on the <span style={{ color: 'var(--cyan)' }}>alternate path</span> —
                checking if the flow can safely pass without causing new congestion.
            </div>

            <div className="bayesian-grid">
                {decisions.map((d, i) => {
                    const isAdmitted = d.admitted
                    const color = isAdmitted ? '#00ff88' : '#ff006e'

                    return (
                        <div key={i} className={`bayes-card ${isAdmitted ? 'admitted' : 'blocked'} fade-in`}>
                            <LAGauge value={d.la ?? 0} color={color} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div className="bayes-link-name">{d.link}</div>
                                <div className="bayes-detail">
                                    PU: <span className="val">{d.pu}%</span> &nbsp;·&nbsp;
                                    RB: <span className="val" style={{ color: d.rb > 0 ? '#00ff88' : '#ff006e' }}>
                                        {d.rb} Mbps
                                    </span> &nbsp;·&nbsp;
                                    Avail: <span className="val">{d.avail_bw} Mbps</span>
                                </div>
                                <div style={{ fontSize: 10, color: isAdmitted ? '#00ff8888' : '#ff006e88', marginTop: 2 }}>
                                    {explainDecision(d)}
                                </div>
                            </div>
                            <span className={`bayes-status ${isAdmitted ? 'admitted' : 'blocked'}`}>
                                {isAdmitted ? '✓ Safe' : '✗ Risky'}
                            </span>
                        </div>
                    )
                })}
            </div>

            {/* Verdict */}
            <div style={{
                marginTop: 8, padding: '8px 12px', borderRadius: 8,
                background: allPass ? 'rgba(0,255,136,0.06)' : 'rgba(255,0,110,0.06)',
                border: `1px solid ${allPass ? 'rgba(0,255,136,0.2)' : 'rgba(255,0,110,0.2)'}`,
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: allPass ? '#00ff88' : '#ff006e' }}>
                        {allPass ? '✓ ROUTE INSTALLED' : '✗ ROUTE REJECTED'}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                        {admitted}/{total} links safe
                    </span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                    {allPass
                        ? 'All links on the alternate path can handle the flow — reroute installed.'
                        : `Blocked: ${blockedLinks.join(', ')} would become congested — flow stays on original path.`
                    }
                </div>
            </div>
        </div>
    )
}
