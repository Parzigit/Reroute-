import React from 'react'

export default function RerouteLog({ history }) {
    if (!history || history.length === 0) {
        return (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 10 }}>
                No rerouting events yet. Waiting for congestion...
            </div>
        )
    }

    const withReroutes = history.filter(c => c.reroutes && c.reroutes.length > 0).reverse()

    if (withReroutes.length === 0) {
        return (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 10 }}>
                Monitoring... no bottlenecks detected yet.
            </div>
        )
    }

    return (
        <div className="reroute-log">
            {withReroutes.slice(0, 20).map((cycle, i) => (
                <div key={i}>
                    {cycle.reroutes.map((r, j) => {
                        const admitted = r.all_admitted

                        return (
                            <div key={`${i}-${j}`} className="reroute-entry fade-in">
                                <div className="reroute-header">
                                    <span className="reroute-time">{cycle.time_str}</span>
                                    <span className="reroute-flow">{r.flow_id}</span>
                                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                        {r.flow_bw} Mbps
                                    </span>
                                    <span className={`reroute-result ${admitted ? 'success' : 'failed'}`}>
                                        {admitted ? '✓ Rerouted' : '✗ Rejected'}
                                    </span>
                                </div>
                                <div className="reroute-detail">
                                    <div>
                                        <span style={{ color: '#ff006e' }}>⚠ Congested:</span>{' '}
                                        <span style={{ color: '#ff006e', fontWeight: 600 }}>{r.bottleneck}</span>
                                        <span style={{ color: 'var(--text-muted)' }}> (PU ≥ 70%)</span>
                                    </div>
                                    <div>
                                        <span style={{ color: 'var(--cyan)' }}>↪ Alternate route:</span>{' '}
                                        <span className="reroute-path">{r.alternate_path}</span>
                                    </div>
                                    <div>
                                        {admitted ? (
                                            <span style={{ color: '#00ff88' }}>
                                                ✓ All {r.passable_count} links safe — flow rerouted successfully
                                            </span>
                                        ) : (
                                            <span style={{ color: '#ff006e' }}>
                                                ✗ {r.impassable_count} link{r.impassable_count > 1 ? 's' : ''} too
                                                congested — flow stays on original path
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )
                    })}
                </div>
            ))}
        </div>
    )
}
