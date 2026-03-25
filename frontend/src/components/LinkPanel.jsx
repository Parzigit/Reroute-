import React from 'react'

function puBarColor(pu) {
    if (pu >= 70) return '#ff006e'
    if (pu >= 50) return '#ffaa00'
    if (pu >= 30) return '#00d4ff'
    return '#00ff88'
}

function LinkEntry({ label, pu, isBn }) {
    const color = puBarColor(pu)
    return (
        <div className={`link-item ${isBn ? 'bottleneck' : ''}`}>
            <span className="link-name">{label}</span>
            <div className="link-bar-wrap">
                <div className="link-bar-fill" style={{
                    width: `${Math.min(pu, 100)}%`,
                    background: `linear-gradient(90deg, ${color}80, ${color})`,
                }} />
            </div>
            <span className="link-pu-val" style={{ color }}>{pu}%</span>
            {isBn && <span className="bottleneck-badge">BN</span>}
        </div>
    )
}

export default function LinkPanel({ topology }) {
    if (!topology || !topology.links) {
        return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No link data</div>
    }

    // Expand each edge into its two directions, each with its own PU
    const rows = []
    for (const link of topology.links) {
        const fwdBn = link.pu_forward >= 70
        const revBn = (link.pu_reverse ?? 0) >= 70

        rows.push({
            label: `${link.source}→${link.target}`,
            pu: link.pu_forward,
            isBn: fwdBn,
        })
        if (link.pu_reverse != null) {
            rows.push({
                label: `${link.target}→${link.source}`,
                pu: link.pu_reverse,
                isBn: revBn,
            })
        }
    }

    // Sort: bottlenecks first, then by PU descending
    rows.sort((a, b) => {
        if (a.isBn !== b.isBn) return b.isBn ? 1 : -1
        return b.pu - a.pu
    })

    return (
        <div className="link-grid">
            {rows.map((r, i) => (
                <LinkEntry key={i} label={r.label} pu={r.pu} isBn={r.isBn} />
            ))}
        </div>
    )
}
