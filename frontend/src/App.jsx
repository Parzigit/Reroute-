import React, { useState, useEffect, useCallback, useRef } from 'react'
import { io } from 'socket.io-client'
import TopologyView from './components/TopologyView'
import LinkPanel from './components/LinkPanel'
import FuzzyPanel from './components/FuzzyPanel'
import UtilizationChart from './components/UtilizationChart'
import RerouteLog from './components/RerouteLog'

const BACKEND = ''
const NODES = ['SE', 'SV', 'LA', 'DE', 'KC', 'HO', 'IN', 'AT', 'CH', 'WA', 'NY']

export default function App() {
    const [topology, setTopology] = useState(null)
    const [stats, setStats] = useState(null)
    const [timeseries, setTimeseries] = useState([])
    const [cycleHistory, setCycleHistory] = useState([])
    const [fuzzyData, setFuzzyData] = useState([])
    const [connected, setConnected] = useState(false)
    const [simSpeed, setSimSpeed] = useState(1.0)
    const socketRef = useRef(null)

    // Inject flow form
    const [injectSrc, setInjectSrc] = useState('SE')
    const [injectDst, setInjectDst] = useState('WA')
    const [injectBw, setInjectBw] = useState('300')

    const fetchData = useCallback(async () => {
        try {
            const [topoRes, statsRes, tsRes, cycleRes, fuzzyRes] = await Promise.all([
                fetch(`${BACKEND}/api/topology`),
                fetch(`${BACKEND}/api/stats/summary`),
                fetch(`${BACKEND}/api/stats/timeseries?limit=60`),
                fetch(`${BACKEND}/api/cycle/history?limit=30`),
                fetch(`${BACKEND}/api/fuzzy/latest`),
            ])
            const [topo, st, ts, cycles, fuzzy] = await Promise.all([
                topoRes.json(), statsRes.json(), tsRes.json(), cycleRes.json(), fuzzyRes.json(),
            ])
            setTopology(topo)
            setStats(st)
            setTimeseries(ts)
            setCycleHistory(cycles)
            setFuzzyData(fuzzy)
        } catch (e) {
            console.error('Fetch error:', e)
        }
    }, [])

    useEffect(() => {
        const socket = io(window.location.origin, { transports: ['websocket', 'polling'] })
        socketRef.current = socket

        socket.on('connect', () => {
            setConnected(true)
            fetchData()
        })
        socket.on('disconnect', () => setConnected(false))
        socket.on('state_update', (data) => {
            if (data.cycle) {
                setCycleHistory(prev => [...prev.slice(-29), data.cycle])
                if (data.cycle.fuzzy_decisions?.length) {
                    setFuzzyData(data.cycle.fuzzy_decisions)
                }
            }
            fetchData()
        })

        return () => socket.disconnect()
    }, [fetchData])

    useEffect(() => {
        const interval = setInterval(fetchData, 2500)
        return () => clearInterval(interval)
    }, [fetchData])

    const changeSpeed = async (speed) => {
        await fetch(`${BACKEND}/api/config/speed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ speed: parseFloat(speed) }),
        })
        setSimSpeed(speed)
    }

    const injectFlow = async () => {
        await fetch(`${BACKEND}/api/simulation/inject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ src: injectSrc, dst: injectDst, bandwidth: parseFloat(injectBw) }),
        })
    }

    const resetSim = async () => {
        await fetch(`${BACKEND}/api/simulation/reset`, { method: 'POST' })
        fetchData()
    }

    return (
        <div className="app">
            {/* Header */}
            <header className="header">
                <div className="header-left">
                    <h1>RyuRoute</h1>
                    <span className="subtitle">Path-Based Proactive Re-routing, Flow Admission and Congestion Propagation</span>
                    <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`}
                        title={connected ? 'Connected' : 'Disconnected'} />
                </div>
                <div className="header-right">
                    <div className="inject-form">
                        <select value={injectSrc} onChange={e => setInjectSrc(e.target.value)}>
                            {NODES.map(n => <option key={n} value={n}>{n}</option>)}
                        </select>
                        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>→</span>
                        <select value={injectDst} onChange={e => setInjectDst(e.target.value)}>
                            {NODES.map(n => <option key={n} value={n}>{n}</option>)}
                        </select>
                        <input type="number" value={injectBw} onChange={e => setInjectBw(e.target.value)}
                            placeholder="Mbps" style={{ width: 60 }} />
                        <button className="btn" onClick={injectFlow}>💉 Inject</button>
                    </div>
                    <select className="btn" value={simSpeed} onChange={e => changeSpeed(e.target.value)}>
                        <option value="0.5">⏱ 0.5x</option>
                        <option value="1">⏱ 1x</option>
                        <option value="2">⏱ 2x</option>
                        <option value="4">⏱ 4x</option>
                    </select>
                    <button className="btn danger" onClick={resetSim}>↺ Reset</button>
                </div>
            </header>

            {/* Main Content */}
            <div className="main-content">
                {/* Stats Row */}
                <div className="stats-row">
                    <div className="glass-card stat-card">
                        <div className="stat-icon cyan">🌐</div>
                        <div className="stat-info">
                            <div className="stat-value">{stats?.total_nodes ?? '-'}</div>
                            <div className="stat-label">Nodes</div>
                        </div>
                    </div>
                    <div className="glass-card stat-card">
                        <div className="stat-icon green">🔗</div>
                        <div className="stat-info">
                            <div className="stat-value">{stats?.total_links ?? '-'}</div>
                            <div className="stat-label">Links</div>
                        </div>
                    </div>
                    <div className="glass-card stat-card">
                        <div className="stat-icon red">⚠️</div>
                        <div className="stat-info">
                            <div className="stat-value">{stats?.bottleneck_count ?? 0}</div>
                            <div className="stat-label">Bottlenecks</div>
                        </div>
                    </div>
                    <div className="glass-card stat-card">
                        <div className="stat-icon amber">📈</div>
                        <div className="stat-info">
                            <div className="stat-value">{stats?.avg_utilization ?? '-'}%</div>
                            <div className="stat-label">Avg PU</div>
                        </div>
                    </div>
                    <div className="glass-card stat-card">
                        <div className="stat-icon purple">🔄</div>
                        <div className="stat-info">
                            <div className="stat-value">{stats?.total_reroutes ?? 0}</div>
                            <div className="stat-label">Reroutes</div>
                        </div>
                    </div>
                </div>

                {/* Topology */}
                <div className="topology-panel glass-card">
                    <div className="card-header">
                        <span className="card-title">🗺 Abilene Network Topology</span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {stats?.active_flows ?? 0} active flows
                        </span>
                    </div>
                    <TopologyView topology={topology} />
                </div>

                {/* Right Panel */}
                <div className="right-panel">
                    <div className="glass-card">
                        <div className="card-header">
                            <span className="card-title">🔮 Fuzzy Flow Admission</span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Mamdani Inference</span>
                        </div>
                        <FuzzyPanel decisions={fuzzyData} />
                    </div>
                    <div className="glass-card">
                        <div className="card-header">
                            <span className="card-title">🔗 Link Utilization</span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                T = 70%
                            </span>
                        </div>
                        <LinkPanel topology={topology} />
                    </div>
                </div>

                {/* Bottom */}
                <div className="bottom-panel">
                    <div className="glass-card">
                        <div className="card-header">
                            <span className="card-title">📊 Utilization Over Time</span>
                        </div>
                        <UtilizationChart timeseries={timeseries} />
                    </div>
                    <div className="glass-card">
                        <div className="card-header">
                            <span className="card-title">📋 Rerouting Log</span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                {cycleHistory.filter(c => c.reroutes?.length).length} events
                            </span>
                        </div>
                        <RerouteLog history={cycleHistory} />
                    </div>
                </div>
            </div>
        </div>
    )
}
