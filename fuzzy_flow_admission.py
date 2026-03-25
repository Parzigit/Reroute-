import random
from sdn_bayesian_system import (
    Link, Flow, NetworkTopology, BottleneckIdentifier,
    AlternatePathComputer, build_abilene_topology,
)

def trimf(x: float, a: float, b: float, c: float) -> float:
    """Triangular membership function — single peak at b."""
    if x <= a or x >= c:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    return (c - x) / (c - b) if c != b else 1.0


def trapmf(x: float, a: float, b: float, c: float, d: float) -> float:
    """Trapezoidal membership function — flat top from b to c."""
    if x <= a or x >= d:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    if x <= c:
        return 1.0
    return (d - x) / (d - c) if d != c else 1.0

def pu_low(x: float) -> float:
    return trapmf(x, -1, 0, 30, 60)

def pu_medium(x: float) -> float:
    return trimf(x, 30, 55, 75)

def pu_high(x: float) -> float:
    return trapmf(x, 60, 80, 100, 101)

def rb_sufficient(x: float) -> float:
    return trapmf(x, 15, 35, 100, 101)

def rb_marginal(x: float) -> float:
    return trimf(x, 0, 10, 25)

def rb_insufficient(x: float) -> float:
    return trapmf(x, -101, -100, 0, 5)


def la_high(x: float) -> float:
    return trapmf(x, 0.6, 0.8, 1.0, 1.01)

def la_medium(x: float) -> float:
    return trimf(x, 0.3, 0.5, 0.7)

def la_low(x: float) -> float:
    return trimf(x, 0.1, 0.25, 0.4)

def la_none(x: float) -> float:
    return trapmf(x, -0.01, 0.0, 0.05, 0.15)


class FuzzyFlowAdmission:
    """
    Pipeline:
        1. Fuzzify PU and RB_norm into membership degrees
        2. Fire rules using AND = min(μ_input1, μ_input2)
        3. Clip + max-aggregate output fuzzy sets
        4. Centroid defuzzification → crisp LA value
        5. Decision: ADMIT if LA > 0.5, BLOCK otherwise
    Rule base:
        R1: IF PU is LOW    AND RB is SUFFICIENT  → LA is HIGH
        R2: IF PU is MEDIUM AND RB is SUFFICIENT  → LA is MEDIUM
        R3: IF PU is HIGH   AND RB is SUFFICIENT  → LA is LOW
        R4: IF PU is LOW    AND RB is MARGINAL    → LA is MEDIUM
        R5: IF PU is MEDIUM AND RB is MARGINAL    → LA is LOW
        R6: IF PU is HIGH   AND RB is MARGINAL    → LA is NONE
        R7: IF RB is INSUFFICIENT                 → LA is NONE
    """
    OUTPUT_STEPS = 201

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.xs = [i / (self.OUTPUT_STEPS - 1) for i in range(self.OUTPUT_STEPS)]

    @staticmethod
    def fuzzify_pu(pu_percent: float) -> dict:
        return {
            "LOW":    pu_low(pu_percent),
            "MEDIUM": pu_medium(pu_percent),
            "HIGH":   pu_high(pu_percent),
        }

    @staticmethod
    def fuzzify_rb(rb_norm: float) -> dict:
        return {
            "SUFFICIENT":   rb_sufficient(rb_norm),
            "MARGINAL":     rb_marginal(rb_norm),
            "INSUFFICIENT": rb_insufficient(rb_norm),
        }

    @staticmethod
    def fire_rules(mu_pu: dict, mu_rb: dict) -> list[tuple[float, callable]]:
        rules = [
            (min(mu_pu["LOW"],    mu_rb["SUFFICIENT"]),   la_high),
            (min(mu_pu["MEDIUM"], mu_rb["SUFFICIENT"]),   la_medium),
            (min(mu_pu["HIGH"],   mu_rb["SUFFICIENT"]),   la_low),
            (min(mu_pu["LOW"],    mu_rb["MARGINAL"]),     la_medium),
            (min(mu_pu["MEDIUM"], mu_rb["MARGINAL"]),     la_low),
            (min(mu_pu["HIGH"],   mu_rb["MARGINAL"]),     la_none),
            (mu_rb["INSUFFICIENT"],                       la_none),
        ]
        return rules

    def aggregate(self, rules: list[tuple[float, callable]]) -> list[float]:
        aggregated = []
        for x in self.xs:
            agg = 0.0
            for strength, output_fn in rules:
                if strength > 0:
                    clipped = min(strength, output_fn(x))
                    agg = max(agg, clipped)
            aggregated.append(agg)
        return aggregated

    def defuzzify_centroid(self, aggregated: list[float]) -> float:
        """Centroid (center of gravity) defuzzification."""
        numerator = sum(x * mu for x, mu in zip(self.xs, aggregated))
        denominator = sum(aggregated)
        if denominator == 0:
            return 0.0 
        return numerator / denominator

    def compute_link_availability(
        self,
        pu_percent: float,
        rb_mbps: float,
        capacity_mbps: float,
    ) -> tuple[float, str, dict]:
        """
        Args:
            pu_percent:    port utilization (0–100%)
            rb_mbps:       residual bandwidth in Mbps (can be negative)
            capacity_mbps: link capacity in Mbps (for normalization)
        Returns:
            (la_crisp, decision, debug_info)
        """
        rb_norm = (rb_mbps / capacity_mbps) * 100.0 if capacity_mbps > 0 else 0.0

        mu_pu = self.fuzzify_pu(pu_percent)
        mu_rb = self.fuzzify_rb(rb_norm)

        rules = self.fire_rules(mu_pu, mu_rb)
        aggregated = self.aggregate(rules)

        la_crisp = self.defuzzify_centroid(aggregated)

        decision = "ADMIT" if la_crisp > self.threshold else "BLOCK"

        debug_info = {
            "pu_percent": pu_percent,
            "rb_mbps": rb_mbps,
            "rb_norm": rb_norm,
            "mu_pu": mu_pu,
            "mu_rb": mu_rb,
            "fired_rules": [
                (f"R{i+1}", strength, output_fn.__name__)
                for i, (strength, output_fn) in enumerate(rules)
                if strength > 0
            ],
            "la_crisp": la_crisp,
            "decision": decision,
        }

        return la_crisp, decision, debug_info

    def evaluate_path(
        self,
        path_links: list[Link],
        flow: Flow,
    ) -> tuple[list[Link], list[Link]]:

        passable: list[Link] = []
        impassable: list[Link] = []

        print(f"\n Evaluating path for flow {flow.flow_id} "
              f"({flow.bandwidth_mbps} Mbps)")

        for link in path_links:
            rb = link.residual_bandwidth(flow.bandwidth_mbps)
            pu = link.port_utilization

            print(f" Link {link.src}→{link.dst}: "
                  f"PU={pu:.1f}%, avail={link.available_bandwidth_mbps:.1f}Mbps, "
                  f"RB={rb:.1f}Mbps", end="")

            if rb <= 0:
                print(f" → RB≤0, BLOCKED (hard)")
                impassable.append(link)
                continue
            la_crisp, decision, debug = self.compute_link_availability(
                pu, rb, link.capacity_mbps
            )
            if decision == "ADMIT":
                print(f" → LA={la_crisp:.3f} > {self.threshold}, ADMITTED")
                passable.append(link)
            else:
                print(f" → LA={la_crisp:.3f} ≤ {self.threshold}, BLOCKED (fuzzy)")
                impassable.append(link)

        return passable, impassable

class FuzzySDNController:
    def __init__(self, topology: NetworkTopology):
        self.topology = topology
        self.module1 = BottleneckIdentifier()
        self.module2 = AlternatePathComputer()
        self.module3 = FuzzyFlowAdmission(threshold=0.5)
        self.max_reroute_attempts = 5

    def run_cycle(self, incoming_flow: Flow):
        print("\n" + "=" * 65)
        print(f" Fuzzy SDN Controller — Processing flow:{incoming_flow}")
        print("=" * 65)
        print("\ Bottleneck Identification")
        bottleneck_links = self.module1.identify(self.topology.links)

        if not bottleneck_links:
            print("  No bottlenecks detected. Routing on default path.")
            return

        for bottleneck in bottleneck_links:
            print(f"\n Alternate Path for bottleneck "
                  f"{bottleneck.src}→{bottleneck.dst}")

            flows_on_link = self.topology.get_flows_on_link(bottleneck)
            largest_flow = self.module2.select_largest_flow(flows_on_link, bottleneck)
            target_flow = largest_flow if largest_flow else incoming_flow

            print(f"Rerouting flow: {target_flow}")

            impassable_accumulator: list[Link] = []
            all_blocked = bottleneck_links.copy()

            for attempt in range(1, self.max_reroute_attempts + 1):
                print(f"\n  Attempt {attempt}:")

                all_blocked_now = list(
                    {(l.src, l.dst): l
                     for l in all_blocked + impassable_accumulator}.values()
                )
                alt_path = self.module2.compute(
                    self.topology.links,
                    all_blocked_now,
                    target_flow.src_node,
                    target_flow.dst_node,
                )

                if alt_path is None:
                    print("  No viable alternate path exists.")
                    break

                print(f"\n Flow Admission")
                path_links = self.module2.get_links_in_path(
                    alt_path, self.topology.links
                )
                passable, impassable = self.module3.evaluate_path(
                    path_links, target_flow
                )

                if not impassable:
                    print(f"\n  All links admitted. Installing path.")
                    self.topology.install_path(target_flow, alt_path)
                    break
                else:
                    print(f"\n  {len(impassable)} link(s) impassable → retry")
                    impassable_accumulator.extend(impassable)
            else:
                print(f"  Max reroute attempts ({self.max_reroute_attempts}) reached.")

        print("\n[DONE]")


