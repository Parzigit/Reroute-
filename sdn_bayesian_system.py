"""
Three-module pipeline:
  Module 1 — Bottleneck Link Identification
  Module 2 — Alternate Path Computation (Dijkstra)
  Module 3 — Bayesian Flow Admission

Requires: networkx  (pip install networkx)
"""
import heapq
import math
import random
from dataclasses import dataclass, field
from typing import Optional

#  DATA STRUCTURES
@dataclass
class Link:
    src: str                    # source node
    dst: str                    # destination node
    capacity_mbps: float        # link capacity in Mbps
    tx_bytes: float = 0.0       # bytes transmitted in last interval (from ofp_port_stats)
    time_interval: float = 10.0 # polling interval in seconds

    @property 
    # port utilisation 
    def port_utilization(self) -> float:
        bits_transmitted = self.tx_bytes * 8
        port_speed_bits = self.capacity_mbps * 1e6
        if port_speed_bits == 0:
            return 0.0
        return (bits_transmitted / (port_speed_bits * self.time_interval))*100.0

    @property
    def available_bandwidth_mbps(self) -> float:
        """Available BW = capacity - currently used BW (derived from tx_bytes)."""
        bits_used = (self.tx_bytes * 8) / self.time_interval  # bits per second
        mbps_used = bits_used / 1e6
        return max(0.0, self.capacity_mbps - mbps_used)

    def residual_bandwidth(self, requested_mbps: float) -> float:
        """
        RB = BW_available - BW_requested
        Positive means the link can accommodate the flow.
        """
        return self.available_bandwidth_mbps - requested_mbps

    def __repr__(self):
        return (f"Link({self.src}→{self.dst} | "
                f"cap={self.capacity_mbps}Mbps | "
                f"PU={self.port_utilization:.1f}% | "
                f"avail={self.available_bandwidth_mbps:.1f}Mbps)")


@dataclass
class Flow:
    flow_id: str
    src_node: str
    dst_node: str
    bandwidth_mbps: float       # bandwidth requested by this flow
    byte_count: float = 0.0    # total bytes so far ( to identify largest flow)

    def __repr__(self):
        return f"Flow({self.flow_id}: {self.src_node}→{self.dst_node}, {self.bandwidth_mbps}Mbps)"


#  MODULE 1 — BOTTLENECK LINK IDENTIFICATION  
class BottleneckIdentifier:
    """
    Periodically monitors port utilization.
    Identifies links as bottleneck if PU >= threshold T.
    Threshold T = 70%
    """

    THRESHOLD_PERCENT: float = 70.0

    def identify(self, links: list[Link]) -> list[Link]:
        """
        BottleneckIdentification()
        Input:  list of all Links with current tx_bytes populated
        Output: BottlenecklinkList BL
        """
        bottleneck_list: list[Link] = []

        for link in links:
            pu = link.port_utilization
            if pu >= self.THRESHOLD_PERCENT: 
                bottleneck_list.append(link) # add to bottleneck list
                print(f" Bottleneck detected: {link.src}→{link.dst} "
                      f"(PU={pu:.1f}% ≥ {self.THRESHOLD_PERCENT}%)")

        return bottleneck_list


#  MODULE 2 — ALTERNATE PATH COMPUTATION
class AlternatePathComputer:
    """
    Updates virtual topology by setting bottleneck (and impassable) link
    weights to infinity, then computes shortest alternate path via Dijkstra.
    """
    INF = float('inf')

    def compute(
        self,
        all_links: list[Link],
        blocked_links: list[Link],
        src: str,
        dst: str
    ) -> Optional[list[str]]:
        """
        AlternatePath(BL or IL)
        Input:  all_links, blocked_links (BL ∪ IL), src_node, dst_node
        Output: list of nodes forming the alternate path, or None

        Set weight of blocked links to infinity in the virtual topology.
        Run Dijkstra's algorithm on modified topology.
        """
        # Build adjacency graph with weights
        # weight = 1 for normal links, infinity for blocked links
        blocked_pairs = {(l.src, l.dst) for l in blocked_links}

        graph: dict[str, list[tuple[float, str]]] = {}
        for link in all_links:
            graph.setdefault(link.src, [])
            graph.setdefault(link.dst, [])
            weight = self.INF if (link.src, link.dst) in blocked_pairs else 1.0
            graph[link.src].append((weight, link.dst))

        # Dijkstra's algorithm
        dist = {node: self.INF for node in graph}
        prev: dict[str, Optional[str]] = {node: None for node in graph}
        dist[src] = 0.0
        pq: list[tuple[float, str]] = [(0.0, src)]

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for w, v in graph.get(u, []):
                if w == self.INF:
                    continue  # skip blocked links
                alt = dist[u] + w
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(pq, (alt, v))

        # Reconstruct path
        if dist.get(dst, self.INF) == self.INF:
            print(f"No alternate path found from {src} to {dst}")
            return None

        path: list[str] = []
        node: Optional[str] = dst
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()

        print(f"Alternate path: {' → '.join(path)}")
        return path

    @staticmethod
    def get_links_in_path(path: list[str], all_links: list[Link]) -> list[Link]:
        """Returns the Link objects corresponding to each hop in the path."""
        link_map = {(l.src, l.dst): l for l in all_links}
        path_links = []
        for i in range(len(path) - 1):
            key = (path[i], path[i + 1])
            if key in link_map:
                path_links.append(link_map[key])
        return path_links

    @staticmethod
    def select_largest_flow(flows: list[Flow], bottleneck_link: Link) -> Optional[Flow]:
        """
        Selects the largest flow through the bottleneck link based on byte count.
        In OpenFlow, this comes from the byte_count field in flow_stat structure.
        """
        if not flows:
            return None
        return max(flows, key=lambda f: f.byte_count)


#  MODULE 3 — BAYESIAN FLOW 
class BayesianFlowAdmission:
    """
    Models a Bayesian Network to decide whether flow admission is possible
    through the alternate path, preventing congestion propagation.

    Bayesian Network structure
        OW → PU ──→ LA ←── RB ←── [BW_available, BW_requested]

    Variables:
        OW  — Observation Window (time context for PU measurement)
        PU  — Port Utilization   (observed, continuous 0–100%)
        RB  — Residual Bandwidth (computed: BW_avail - BW_req; binary P(RB)=0 or 1)
        LA  — Link Availability  (latent: what we're inferring)

    Bayes' theorem:
        P(LA | RB, PU) = P(RB, PU | LA) × P(LA) / (P(RB) × P(PU))

    Decision rule: admit if P(LA) > (1 - P(LA)), i.e., P(LA) > 0.5
    """

    def __init__(self, prior_la: float = 0.5):
        """
        Defaults to 0.5
        """
        self.prior_la = prior_la

    # Conditional probability tables
    def p_rb_given_la(self, rb_positive: bool, la: int) -> float:
        """
        P(RB | LA) — likelihood of the RB outcome given link availability.
        Intuition:
          - If the link IS available (la=1), it's very likely RB is positive (we
            expect available links to have headroom). P(RB=1|LA=1) = 0.9
          - If the link is NOT available (la=0), residual BW is unlikely.
            P(RB=1|LA=0) = 0.1
        """
        if rb_positive:
            return 0.9 if la == 1 else 0.1
        else:
            return 0.1 if la == 1 else 0.9

    def p_pu_given_la(self, pu_percent: float, la: int) -> float:
        """
        P(PU | LA) — likelihood of the observed port utilization given availability.
        Intuition:
          - If the link IS available (la=1), we expect LOW utilization.
            Model as: P(PU | LA=1) = 1 - (PU/100) (higher PU → less likely to be available)
          - If the link is NOT available (la=0), we expect HIGH utilization.
            Model as: P(PU | LA=0) = PU/100
        """
        pu_norm = pu_percent / 100.0  # normalize to [0, 1]
        if la == 1:
            return max(0.01, min(0.99, 1.0 - pu_norm))
        else:
            return max(0.01, min(0.99, pu_norm))

    # Bayesian computation 
    def compute_link_availability(
        self,
        pu_percent: float,
        rb_positive: bool
    ) -> float:
        """
        Compute P(LA=1 | RB, PU).

        P(LA | RB, PU) = P(RB, PU | LA) × P(LA) / (P(RB) × P(PU))

        Assuming RB ⊥ PU | LA (conditional independence), the joint likelihood:
            P(RB, PU | LA) = P(RB | LA) × P(PU | LA)

        Returns the posterior probability that the link is available.
        """
        p_la_1 = self.prior_la       # P(LA=1)
        p_la_0 = 1.0 - self.prior_la  # P(LA=0)

        # Likelihoods
        p_rb_pu_given_la1 = (self.p_rb_given_la(rb_positive, la=1) *
                              self.p_pu_given_la(pu_percent, la=1))
        p_rb_pu_given_la0 = (self.p_rb_given_la(rb_positive, la=0) *
                              self.p_pu_given_la(pu_percent, la=0))

        # Marginal evidence P(RB, PU) — denominator/normalizer
        p_rb_pu = (p_rb_pu_given_la1 * p_la_1) + (p_rb_pu_given_la0 * p_la_0)

        if p_rb_pu == 0:
            return 0.0  # degenerate case

        # Posterior via Bayes' theorem — Formula (3)
        p_la_given_rb_pu = (p_rb_pu_given_la1 * p_la_1) / p_rb_pu

        return p_la_given_rb_pu

    def evaluate_path(
        self,
        path_links: list[Link],
        flow: Flow
    ) -> tuple[list[Link], list[Link]]:
        """
        FlowAdmission()
        Input:  path_links (links in the alternate path), flow (with BW request)
        Output: (passable_links, impassable_links IL)

        For each link in the alternate path:
          1. Compute RB = BW_available - BW_requested
          2. If RB <= 0: add to IL immediately (hard block)
          3. If RB > 0: P(RB) = 1, run Bayesian inference
          4. If P(LA) <= 0.5: add to IL , else LA=1
        """
        impassable: list[Link] = []
        passable:   list[Link] = []

        print(f"\n Evaluating path for flow {flow.flow_id} "
              f"({flow.bandwidth_mbps} Mbps)")

        for link in path_links:
            rb = link.residual_bandwidth(flow.bandwidth_mbps) 
            pu = link.port_utilization

            print(f"    Link {link.src}→{link.dst}: "
                  f"PU={pu:.1f}%, avail={link.available_bandwidth_mbps:.1f}Mbps, "
                  f"RB={rb:.1f}Mbps", end="")

            if rb <= 0:
                print(f" → RB≤0, BLOCKED (hard)")
                impassable.append(link)
                continue

            rb_positive = True

            p_la = self.compute_link_availability(pu, rb_positive)

            if p_la > (1.0 - p_la):  # P(LA) > 0.5
                print(f" → P(LA)={p_la:.3f} > 0.5, ADMITTED (LA=1)")
                passable.append(link)
            else:
                print(f" → P(LA)={p_la:.3f} ≤ 0.5, BLOCKED (Bayesian)")
                impassable.append(link)

        return passable, impassable


#  NETWORK TOPOLOGY
class NetworkTopology:
    """
    Manages the network's link state and flow table.
    Simulates the SDN controller's global view of the data plane.
    """

    def __init__(self):
        self.links: list[Link] = []
        self.flows: dict[str, list[Flow]] = {}  # link_key → flows using that link
        self.flow_table: list[tuple[str, str, list[str]]] = []  # installed (src, dst, path)

    def add_link(self, src: str, dst: str, capacity_mbps: float):
        """Adds a bidirectional link (two directed links)."""
        self.links.append(Link(src, dst, capacity_mbps))
        self.links.append(Link(dst, src, capacity_mbps))

    def set_link_load(self, src: str, dst: str, tx_bytes: float):
        """Updates tx_bytes for a link (simulates OpenFlow port stats reply)."""
        for link in self.links:
            if link.src == src and link.dst == dst:
                link.tx_bytes = tx_bytes
                return
        print(f"  Warning: link {src}→{dst} not found")

    def add_flow_on_link(self, src: str, dst: str, flow: Flow):
        """Associates a flow with a link (for largest-flow selection)."""
        key = f"{src}→{dst}"
        self.flows.setdefault(key, []).append(flow)

    def get_flows_on_link(self, link: Link) -> list[Flow]:
        key = f"{link.src}→{link.dst}"
        return self.flows.get(key, [])

    def install_path(self, flow: Flow, path: list[str]):
        """Simulates installing flow table entries on all switches in the path."""
        self.flow_table.append((flow.src_node, flow.dst_node, path))
        print(f"  [Flow Table] Installed: {flow.flow_id} via {' → '.join(path)}")


class SDNController:

    def __init__(self, topology: NetworkTopology):
        self.topology = topology
        self.module1 = BottleneckIdentifier()
        self.module2 = AlternatePathComputer()
        self.module3 = BayesianFlowAdmission(prior_la=0.5)
        self.max_reroute_attempts = 5  # prevent infinite loops

    def run_cycle(self, incoming_flow: Flow):

        print("\n" + "=" * 65)
        print(f" SDN Controller — Processing flow: {incoming_flow}")
        print("=" * 65)

        # ── Module 1:Identify bottleneck links ──────────────────────────────
        print("\n[MODULE 1] Bottleneck Identification")
        bottleneck_links = self.module1.identify(self.topology.links)

        if not bottleneck_links:
            print("  No bottlenecks detected. Routing on default path.")
            return

        # For each bottleneck, try to reroute its largest flow
        # (In the paper, the largest flow through the bottleneck is rerouted)
        for bottleneck in bottleneck_links:
            print(f"\n[MODULE 2] Alternate Path Computation for bottleneck {bottleneck.src}→{bottleneck.dst}")

            # Select largest flow through this bottleneck
            flows_on_link = self.topology.get_flows_on_link(bottleneck)
            largest_flow = self.module2.select_largest_flow(flows_on_link, bottleneck)
            target_flow = largest_flow if largest_flow else incoming_flow

            print(f"  Rerouting flow: {target_flow}")

            # Iterative rerouting loop (handles cascading impassable links)
            impassable_accumulator: list[Link] = []
            all_blocked = bottleneck_links.copy()

            for attempt in range(1, self.max_reroute_attempts + 1):
                print(f"\n  Attempt {attempt}:")

                # ── Module 2: Compute alternate path ─────────────────────────
                all_blocked_now = list({(l.src, l.dst): l for l in all_blocked + impassable_accumulator}.values())
                alt_path = self.module2.compute(
                    self.topology.links,
                    all_blocked_now,
                    target_flow.src_node,
                    target_flow.dst_node
                )

                if alt_path is None:
                    print("  No viable alternate path exists. Keeping original route.")
                    break

                # ── Module 3: Bayesian flow admission ────────────────────────
                print(f"\n[MODULE 3] Bayesian Flow Admission")
                path_links = self.module2.get_links_in_path(alt_path, self.topology.links)
                passable, impassable = self.module3.evaluate_path(path_links, target_flow)

                if not impassable:
                    # All links in alternate path cleared Bayesian gate
                    print(f"\n  All links admitted. Installing path.")
                    self.topology.install_path(target_flow, alt_path)
                    break
                else:
                    # Some links failed: feed back into Module 2 (Algorithm 3, line 18-19)
                    print(f"\n  {len(impassable)} link(s) impassable → calling AlternatePath(IL)")
                    impassable_accumulator.extend(impassable)
            else:
                print(f"  Max reroute attempts ({self.max_reroute_attempts}) reached.")

        print("\n[DONE]")


def build_abilene_topology() -> NetworkTopology:
    """
    Simplified Abilene-inspired 11-node topology.
    Matches the simulation topology described in Section 4 of the paper.

    Nodes: Seattle(SE), Sunnyvale(SV), LosAngeles(LA), Denver(DE), Houston(HO),
           KansasCity(KC), Indianapolis(IN), Atlanta(AT), Chicago(CH),
           Washington(WA), NewYork(NY)
    """
    topo = NetworkTopology()

    # 1 Gbps links (capacity in Mbps)
    CAPACITY = 1000.0

    edges = [
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

    for src, dst in edges:
        topo.add_link(src, dst, CAPACITY)

    return topo

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_tests()
    else:
        random.seed(42)
        run_demo()
        print()
        run_tests()
