import React, { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'

const LINK_COLORS = {
    'SE→SV': '#00d4ff',
    'SE→DE': '#ff006e',
    'SV→LA': '#00ff88',
    'LA→HO': '#ffaa00',
    'DE→KC': '#a855f7',
    'KC→HO': '#f97316',
    'HO→AT': '#06b6d4',
    'KC→IN': '#ec4899',
    'IN→WA': '#84cc16',
    'AT→WA': '#f43e5c',
    'CH→NY': '#8b5cf6',
    'WA→NY': '#14b8a6',
    'SV→DE': '#e879f9',
    'KC→CH': '#fbbf24',
    'IN→AT': '#38bdf8',
}

// Show only the most interesting links (those that get congested)
const DISPLAY_LINKS = ['SE→SV', 'KC→HO', 'LA→HO', 'AT→WA', 'DE→KC', 'SV→LA']

export default function UtilizationChart({ timeseries }) {
    const chartData = useMemo(() => {
        if (!timeseries || timeseries.length === 0) return { data: [], keys: [] }

        const data = timeseries.map((snap, i) => {
            const point = { idx: i }
            if (snap.links) {
                DISPLAY_LINKS.forEach(key => {
                    if (snap.links[key] !== undefined) {
                        point[key] = snap.links[key]
                    }
                })
            }
            return point
        })

        return { data, keys: DISPLAY_LINKS }
    }, [timeseries])

    if (chartData.data.length === 0) {
        return (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: 20, textAlign: 'center' }}>
                Collecting utilization data...
            </div>
        )
    }

    return (
        <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData.data} margin={{ top: 5, right: 10, left: -15, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="idx" tick={false} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} />
                    <YAxis domain={[0, 100]}
                        tick={{ fill: '#555', fontSize: 10 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                    />
                    <Tooltip
                        contentStyle={{
                            background: 'rgba(6,8,26,0.96)',
                            border: '1px solid rgba(0,212,255,0.25)',
                            borderRadius: 8, fontSize: 11, color: '#e8e8f0',
                        }}
                        labelStyle={{ display: 'none' }}
                    />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    {/* Threshold line at 70% */}
                    <ReferenceLine y={70} stroke="#ff006e" strokeDasharray="4 4"
                        strokeOpacity={0.4} label={{ value: 'T=70%', fill: '#ff006e80', fontSize: 9, position: 'right' }}
                    />
                    {chartData.keys.map(key => (
                        <Line key={key} type="monotone" dataKey={key}
                            stroke={LINK_COLORS[key] || '#888'}
                            strokeWidth={1.5} dot={false}
                            animationDuration={300}
                        />
                    ))}
                </LineChart>
            </ResponsiveContainer>
        </div>
    )
}
