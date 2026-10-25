
import random
import statistics

from backend.services.optimizer import solve_vrp


def make_scenario(seed, customer_count=6, partner_count=2):
    """Create a reproducible synthetic delivery scenario."""
    rng = random.Random(seed)

    # Node layout required by the existing solver:
    # [partners][duplicated shop nodes][customers]
    n = 2 * partner_count + customer_count

    durations = [[0.0] * n for _ in range(n)]
    costs = [[0.0] * n for _ in range(n)]

    # Create reproducible travel times. The same matrices are used
    # by the baseline and optimized route.
    for i in range(n):
        for j in range(n):
            if i == j:
                continue

            base = rng.uniform(5, 30)
            durations[i][j] = base
            costs[i][j] = base

    # Partner-to-shop travel should be a valid first leg.
    for p in range(partner_count):
        shop_node = partner_count + p
        durations[p][shop_node] = 3.0
        costs[p][shop_node] = 3.0

    # Assign customers to partners in a balanced, deterministic way.
    allowed = [[] for _ in range(partner_count)]
    customer_start = 2 * partner_count

    for c in range(customer_count):
        partner = c % partner_count
        allowed[partner].append(customer_start + c)

    return costs, durations, allowed, partner_count


def baseline_time(durations, allowed, partner_count):
    """Original customer-index order, measured across all vehicles."""
    total = 0.0
    customer_start = 2 * partner_count

    for partner, customers in enumerate(allowed):
        if not customers:
            continue

        route = [partner, partner_count + partner] + customers
        total += sum(
            durations[a][b]
            for a, b in zip(route, route[1:])
        )

    return total


def optimized_time(costs, durations, allowed, partner_count):
    """Run the RouteIQ OR-Tools solver on the canonical travel-time matrix."""
    starts = list(range(partner_count))
    ends = list(range(partner_count))

    routes = solve_vrp(
        costs,
        durations,
        delay_threshold=300.0,
        delay_penalty_cost=0.0,
        num_vehicles=partner_count,
        starts=starts,
        ends=ends,
        vehicle_allowed_customers=allowed,
    )

    if not routes:
        raise RuntimeError("OR-Tools failed to produce a solution.")

    total = 0.0
    customer_start = 2 * partner_count

    for route in routes:
        if not any(node >= customer_start for node in route):
            continue

        route = route[:-1] if len(route) > 1 and route[-1] == route[0] else route
        total += sum(durations[a][b] for a, b in zip(route, route[1:]))

    return total


def main():
    results = []

    for seed in range(10):
        costs, durations, allowed, partners = make_scenario(seed)

        baseline = baseline_time(durations, allowed, partners)
        optimized = optimized_time(costs, durations, allowed, partners)

        reduction = (
            (baseline - optimized) / baseline * 100
            if baseline > 0 else 0.0
        )

        results.append(reduction)

        print(
            f"Scenario {seed + 1:02d}: "
            f"baseline={baseline:.2f} min, "
            f"optimized={optimized:.2f} min, "
            f"reduction={reduction:.2f}%"
        )

    print("\n--- Summary ---")
    print(f"Scenarios: {len(results)}")
    print(f"Mean reduction: {statistics.mean(results):.2f}%")
    print(f"Median reduction: {statistics.median(results):.2f}%")
    print(f"Scenarios with improvement: {sum(r > 0 for r in results)}/{len(results)}")


if __name__ == "__main__":
    main()
