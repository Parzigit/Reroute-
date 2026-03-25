import time
import random
import threading
import logging
import math
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO

from sdn_bayesian_system import (
    Link, Flow, NetworkTopology, SDNController,
    BottleneckIdentifier, AlternatePathComputer, BayesianFlowAdmission,
    build_abilene_topology,
)

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sdn_bayesian")


sim_lock = threading.Lock()
polling_interval = 1.5
cycle_count = 0

NODE_POSITIONS = {
    "SE": {"x": 80,  "y": 120, "label": "Seattle"},
    "SV": {"x": 80,  "y": 320, "label": "Sunnyvale"},
    "LA": {"x": 160, "y": 480, "label": "Los Angeles"},
    "DE": {"x": 300, "y": 180, "label": "Denver"},
    "KC": {"x": 440, "y": 280, "label": "Kansas City"},
    "HO": {"x": 380, "y": 460, "label": "Houston"},
    "IN": {"x": 560, "y": 220, "label": "Indianapolis"},
    "AT": {"x": 580, "y": 420, "label": "Atlanta"},
    "CH": {"x": 540, "y": 100, "label": "Chicago"},
    "WA": {"x": 700, "y": 300, "label": "Washington"},
    "NY": {"x": 760, "y": 140, "label": "New York"},
}

ABILENE_EDGES = [
    ("SE", "SV"), ("SE", "DE"),
    ("SV", "LA"), ("SV", "DE"),
    ("LA", "HO"),
    ("DE", "KC"),
    ("HO", "KC"), ("HO", "AT"),
    ("KC", "IN"), ("KC", "CH"),
    ("IN", "AT"), ("IN", "WA"),
    ("AT", "WA"),
    ("CH", "NY"),
    ("WA", "NY"),
]


class SimulationEngine:
    def __init__(self):
        self.topology = build_abilene_topology()
        self.module1 = BottleneckIdentifier()
        self.module2 = AlternatePathComputer()
        self.module3 = BayesianFlowAdmission(prior_la=0.5)

        # State
        self.link_loads = {}           # (src,dst) → PU%
        self.timeseries = []           # historical snapshots
        self.max_timeseries = 120
        self.cycle_history = []        # rerouting events
        self.flow_table = []           # installed paths
        self.current_flows = []        # active flows
        self.active_path = None        # currently highlighted path
        self.active_bottlenecks = []   # currently detected bottlenecks
        self.bayesian_results = []     # latest Bayesian evaluation
        self.tick = 0
        self._randomize_loads()
        self._setup_flows()

    def _setup_flows(self):
        """Set up initial flows for the simulation."""
        self.current_flows = [
            Flow("F1", "SE", "WA", 200.0, byte_count=5_000_000),
            Flow("F2", "SE", "NY", 150.0, byte_count=3_000_000),
            Flow("F3", "LA", "NY", 180.0, byte_count=4_000_000),
        ]
        # Associate F1 with SE→SV
        self.topology.add_flow_on_link("SE", "SV", self.current_flows[0])

    def _randomize_loads(self):
        """Generate dynamic traffic patterns that create interesting congestion."""
        interval = 10.0

        def bytes_for_pu(pu, cap=1000.0):
            return (pu / 100.0) * (cap * 1e6) * interval / 8

        self.tick += 1
        t = self.tick * 0.15

        # Create dynamic patterns with some links getting congested
        load_patterns = {
            ("SE", "SV"): 55 + 30 * math.sin(t * 0.7) + random.uniform(-5, 5),
            ("SV", "SE"): 30 + 10 * math.sin(t * 0.5) + random.uniform(-3, 3),
            ("SE", "DE"): 25 + 15 * math.sin(t * 0.3 + 1) + random.uniform(-3, 3),
            ("DE", "SE"): 20 + 10 * math.sin(t * 0.4) + random.uniform(-2, 2),
            ("SV", "LA"): 35 + 20 * math.sin(t * 0.6 + 0.5) + random.uniform(-4, 4),
            ("LA", "SV"): 25 + 10 * math.sin(t * 0.5 + 1) + random.uniform(-3, 3),
            ("SV", "DE"): 30 + 15 * math.sin(t * 0.4 + 2) + random.uniform(-3, 3),
            ("DE", "SV"): 25 + 10 * math.sin(t * 0.3 + 1) + random.uniform(-2, 2),
            ("LA", "HO"): 40 + 25 * math.sin(t * 0.5 + 1.5) + random.uniform(-4, 4),
            ("HO", "LA"): 30 + 15 * math.sin(t * 0.6 + 2) + random.uniform(-3, 3),
            ("DE", "KC"): 35 + 20 * math.sin(t * 0.4 + 0.8) + random.uniform(-3, 3),
            ("KC", "DE"): 30 + 15 * math.sin(t * 0.5 + 1.2) + random.uniform(-3, 3),
            ("KC", "HO"): 50 + 25 * math.sin(t * 0.8 + 2) + random.uniform(-4, 4),
            ("HO", "KC"): 35 + 15 * math.sin(t * 0.6 + 1) + random.uniform(-3, 3),
            ("HO", "AT"): 40 + 20 * math.sin(t * 0.5 + 1) + random.uniform(-4, 4),
            ("AT", "HO"): 30 + 15 * math.sin(t * 0.4 + 2) + random.uniform(-3, 3),
            ("KC", "IN"): 30 + 15 * math.sin(t * 0.3 + 1) + random.uniform(-3, 3),
            ("IN", "KC"): 25 + 10 * math.sin(t * 0.4 + 0.5) + random.uniform(-2, 2),
            ("KC", "CH"): 35 + 20 * math.sin(t * 0.5 + 2) + random.uniform(-3, 3),
            ("CH", "KC"): 25 + 15 * math.sin(t * 0.4 + 1) + random.uniform(-3, 3),
            ("IN", "AT"): 30 + 15 * math.sin(t * 0.6 + 1.5) + random.uniform(-3, 3),
            ("AT", "IN"): 25 + 10 * math.sin(t * 0.5 + 2) + random.uniform(-2, 2),
            ("IN", "WA"): 35 + 20 * math.sin(t * 0.4 + 0.8) + random.uniform(-3, 3),
            ("WA", "IN"): 30 + 15 * math.sin(t * 0.3 + 1.5) + random.uniform(-3, 3),
            ("AT", "WA"): 40 + 25 * math.sin(t * 0.7 + 1) + random.uniform(-4, 4),
            ("WA", "AT"): 30 + 15 * math.sin(t * 0.5 + 2) + random.uniform(-3, 3),
            ("CH", "NY"): 35 + 20 * math.sin(t * 0.6 + 1.5) + random.uniform(-3, 3),
            ("NY", "CH"): 25 + 15 * math.sin(t * 0.5 + 1) + random.uniform(-3, 3),
            ("WA", "NY"): 30 + 15 * math.sin(t * 0.3 + 2) + random.uniform(-3, 3),
            ("NY", "WA"): 25 + 10 * math.sin(t * 0.4 + 0.5) + random.uniform(-2, 2),
        }

        for (src, dst), pu in load_patterns.items():
            pu_clamped = max(5.0, min(98.0, pu))
            self.topology.set_link_load(src, dst, bytes_for_pu(pu_clamped))
            self.link_loads[(src, dst)] = pu_clamped

    def take_snapshot(self):
        """Capture current state for timeseries."""
        link_data = {}
        for link in self.topology.links:
            key = f"{link.src}→{link.dst}"
            link_data[key] = round(link.port_utilization, 1)

        snapshot = {
            "tick": self.tick,
            "links": link_data,
            "bottleneck_count": len(self.active_bottlenecks),
            "flow_count": len(self.current_flows),
        }
        self.timeseries.append(snapshot)
        if len(self.timeseries) > self.max_timeseries:
            self.timeseries = self.timeseries[-self.max_timeseries:]
        return snapshot

    def run_cycle(self):
        """Run one rerouting cycle and return structured results."""
        global cycle_count
        self._randomize_loads()

        # Module 1: Identify bottlenecks
        bottlenecks = self.module1.identify(self.topology.links)
        self.active_bottlenecks = [
            {"src": b.src, "dst": b.dst, "pu": round(b.port_utilization, 1)}
            for b in bottlenecks
        ]

        cycle_result = {
            "cycle_id": cycle_count,
            "timestamp": time.time(),
            "time_str": time.strftime("%H:%M:%S"),
            "bottlenecks": self.active_bottlenecks,
            "reroutes": [],
            "bayesian_decisions": [],
        }

        if bottlenecks:
            # Pick a flow to reroute
            flow = random.choice(self.current_flows)

            for bn in bottlenecks:
                # Module 2: Compute alternate path
                alt_path = self.module2.compute(
                    self.topology.links,
                    [bn],
                    flow.src_node,
                    flow.dst_node,
                )

                if alt_path:
                    self.active_path = alt_path

                    # Module 3: Bayesian flow admission
                    path_links = self.module2.get_links_in_path(alt_path, self.topology.links)
                    passable, impassable = self.module3.evaluate_path(path_links, flow)

                    bayes_decisions = []
                    for link in path_links:
                        pu = link.port_utilization
                        rb = link.residual_bandwidth(flow.bandwidth_mbps)
                        rb_positive = rb > 0

                        if rb_positive:
                            p_la = self.module3.compute_link_availability(pu, True)
                        else:
                            p_la = 0.0

                        decision = "BLOCKED (RB≤0)" if rb <= 0 else (
                            "ADMITTED" if p_la > 0.5 else "BLOCKED (Bayesian)"
                        )
                        bayes_decisions.append({
                            "link": f"{link.src}→{link.dst}",
                            "src": link.src,
                            "dst": link.dst,
                            "pu": round(pu, 1),
                            "avail_bw": round(link.available_bandwidth_mbps, 1),
                            "rb": round(rb, 1),
                            "p_la": round(p_la, 4),
                            "decision": decision,
                            "admitted": decision == "ADMITTED",
                        })

                    self.bayesian_results = bayes_decisions
                    all_admitted = len(impassable) == 0

                    reroute = {
                        "flow_id": flow.flow_id,
                        "flow_bw": flow.bandwidth_mbps,
                        "bottleneck": f"{bn.src}→{bn.dst}",
                        "alternate_path": " → ".join(alt_path),
                        "path_nodes": alt_path,
                        "bayesian_decisions": bayes_decisions,
                        "all_admitted": all_admitted,
                        "passable_count": len(passable),
                        "impassable_count": len(impassable),
                    }

                    if all_admitted:
                        self.flow_table.append({
                            "flow_id": flow.flow_id,
                            "path": alt_path,
                            "time_str": time.strftime("%H:%M:%S"),
                        })

                    cycle_result["reroutes"].append(reroute)
                    cycle_result["bayesian_decisions"] = bayes_decisions

        self.cycle_history.append(cycle_result)
        if len(self.cycle_history) > 100:
            self.cycle_history = self.cycle_history[-100:]

        cycle_count += 1
        return cycle_result


# ─── Create Engine ────────────────────────────────────────────────────────────

engine = SimulationEngine()

# ─── REST API ─────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "topology": "abilene"})


@app.route("/api/topology")
def get_topology():
    """Return nodes, links, and positions for the Abilene topology."""
    nodes = []
    for node_id, pos in NODE_POSITIONS.items():
        nodes.append({
            "id": node_id,
            "x": pos["x"],
            "y": pos["y"],
            "label": pos["label"],
        })

    links = []
    with sim_lock:
        for link in engine.topology.links:
            if link.src < link.dst:
                is_bottleneck = any(
                    b["src"] == link.src and b["dst"] == link.dst
                    for b in engine.active_bottlenecks
                )
                reverse_bottleneck = any(
                    b["src"] == link.dst and b["dst"] == link.src
                    for b in engine.active_bottlenecks
                )
                links.append({
                    "source": link.src,
                    "target": link.dst,
                    "pu_forward": round(link.port_utilization, 1),
                    "avail_forward": round(link.available_bandwidth_mbps, 1),
                    "is_bottleneck": is_bottleneck or reverse_bottleneck,
                })

        active_path = engine.active_path

    return jsonify({
        "topology_name": "Abilene",
        "nodes": nodes,
        "links": links,
        "active_path": active_path,
    })


@app.route("/api/links")
def get_links():
    """Return detailed link data."""
    with sim_lock:
        result = []
        for link in engine.topology.links:
            is_bottleneck = link.port_utilization >= 70.0
            result.append({
                "src": link.src,
                "dst": link.dst,
                "direction": f"{link.src}→{link.dst}",
                "capacity_mbps": link.capacity_mbps,
                "pu": round(link.port_utilization, 1),
                "avail_bw": round(link.available_bandwidth_mbps, 1),
                "tx_bytes": link.tx_bytes,
                "is_bottleneck": is_bottleneck,
            })
    return jsonify(result)


@app.route("/api/stats/summary")
def get_stats_summary():
    """Return aggregate stats for the dashboard stat cards."""
    with sim_lock:
        all_pu = [l.port_utilization for l in engine.topology.links]
        avg_pu = sum(all_pu) / len(all_pu) if all_pu else 0
        bottleneck_count = sum(1 for pu in all_pu if pu >= 70.0)
        return jsonify({
            "total_nodes": len(NODE_POSITIONS),
            "total_links": len(engine.topology.links) // 2,  # bidirectional
            "avg_utilization": round(avg_pu, 1),
            "bottleneck_count": bottleneck_count // 2,  # bidirectional
            "total_reroutes": sum(1 for c in engine.cycle_history if c.get("reroutes")),
            "installed_paths": len(engine.flow_table),
            "active_flows": len(engine.current_flows),
        })


@app.route("/api/stats/timeseries")
def get_timeseries():
    """Return time-series data for charts."""
    limit = request.args.get("limit", 60, type=int)
    with sim_lock:
        data = engine.timeseries[-limit:]
    return jsonify(data)


@app.route("/api/cycle/history")
def get_cycle_history():
    """Return rerouting cycle log."""
    limit = request.args.get("limit", 50, type=int)
    with sim_lock:
        data = engine.cycle_history[-limit:]
    return jsonify(data)


@app.route("/api/bayesian/latest")
def get_bayesian_latest():
    """Return latest Bayesian evaluation results."""
    with sim_lock:
        return jsonify(engine.bayesian_results)


@app.route("/api/flows")
def get_flows():
    """Return active flows and flow table."""
    with sim_lock:
        flows = [
            {
                "flow_id": f.flow_id,
                "src": f.src_node,
                "dst": f.dst_node,
                "bw_mbps": f.bandwidth_mbps,
                "byte_count": f.byte_count,
            }
            for f in engine.current_flows
        ]
        return jsonify({
            "active_flows": flows,
            "flow_table": engine.flow_table[-20:],
        })


@app.route("/api/config/speed", methods=["POST"])
def config_speed():
    """Adjust the simulation speed."""
    global polling_interval
    body = request.get_json(silent=True) or {}
    speed = float(body.get("speed", 1.0))
    if speed > 0:
        polling_interval = 1.5 / speed
    return jsonify({"speed": speed, "interval": polling_interval})


@app.route("/api/simulation/inject", methods=["POST"])
def inject_flow():
    """Inject a new flow into the simulation."""
    body = request.get_json(silent=True) or {}
    src = body.get("src", "SE")
    dst = body.get("dst", "WA")
    bw = float(body.get("bandwidth", 300))
    flow_id = f"F_inj_{int(time.time()) % 10000}"

    with sim_lock:
        new_flow = Flow(flow_id, src, dst, bw, byte_count=random.randint(1_000_000, 10_000_000))
        engine.current_flows.append(new_flow)

    return jsonify({"flow_id": flow_id, "src": src, "dst": dst, "bandwidth": bw})


@app.route("/api/simulation/reset", methods=["POST"])
def reset_simulation():
    """Reset the simulation to initial state."""
    global engine, cycle_count
    with sim_lock:
        engine = SimulationEngine()
        cycle_count = 0
    return jsonify({"status": "reset"})


# ─── WebSocket ────────────────────────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    logger.info("Client connected: %s", request.sid)


@socketio.on("disconnect")
def handle_disconnect():
    logger.info("Client disconnected: %s", request.sid)


# ─── Background Simulation Loop ──────────────────────────────────────────────

def simulation_loop():
    """Background thread running continuous simulation cycles."""
    while True:
        time.sleep(polling_interval)

        with sim_lock:
            snapshot = engine.take_snapshot()
            cycle_result = engine.run_cycle()

        socketio.emit("state_update", {
            "snapshot": snapshot,
            "cycle": cycle_result,
        })


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("SDN Bayesian Congestion Control Dashboard")
    logger.info("Path-Based Proactive Re-routing with Bayesian Network")
    logger.info("=" * 60)

    bg_thread = threading.Thread(target=simulation_loop, daemon=True)
    bg_thread.start()

    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
