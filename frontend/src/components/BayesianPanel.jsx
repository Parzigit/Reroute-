import React from 'react'

function ProbGauge({ value, color }) {
    // Semicircular gauge for P(LA)
    const pct = Math.max(0, Math.min(1, value))
    const angle = pct * 180
    const r = 18
    const cx = 22
    const cy = 22

    // Arc from left (180°) sweeping clockwise by `angle` degrees
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
                {/* Background arc */}
                <path
                    d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
                    fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={4}
                    strokeLinecap="round"
                />
                {/* Value arc */}
                {pct > 0.01 && (
                    <path
                        d={`M ${startX} ${startY} A ${r} ${r} 0 ${largeArc} 1 ${endX} ${endY}`}
                        fill="none" stroke={color} strokeWidth={4}
                        strokeLinecap="round" strokeOpacity={0.9}
                    />
                )}
                {/* Center text */}
                <text x={cx} y={cy - 2} textAnchor="middle"
                    className="bayes-gauge-text" fill={color}>
                    {(pct * 100).toFixed(0)}%
                </text>
            </svg>
        </div>
    )
}

export default function BayesianPanel({ decisions }) {
    if (!decisions || decisions.length === 0) {
        return (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 16, textAlign: 'center' }}>
                Waiting for Bayesian evaluation...
            </div>
        )
    }

    return (
        <div className="bayesian-grid">
            {decisions.map((d, i) => {
                const isAdmitted = d.admitted
                const color = isAdmitted ? '#00ff88' : '#ff006e'

                return (
                    <div key={i} className={`bayes-card ${isAdmitted ? 'admitted' : 'blocked'} fade-in`}>
                        <ProbGauge value={d.p_la} color={color} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div className="bayes-link-name">{d.link}</div>
                            <div className="bayes-detail">
                                PU: <span className="val">{d.pu}%</span> &nbsp;·&nbsp;
                                RB: <span className="val" style={{ color: d.rb > 0 ? '#00ff88' : '#ff006e' }}>
                                    {d.rb} Mbps
                                </span> &nbsp;·&nbsp;
                                Avail: <span className="val">{d.avail_bw} Mbps</span>
                            </div>
                        </div>
                        <span className={`bayes-status ${isAdmitted ? 'admitted' : 'blocked'}`}>
                            {isAdmitted ? '✓ Pass' : '✗ Block'}
                        </span>
                    </div>
                )
            })}
        </div>
    )
}
