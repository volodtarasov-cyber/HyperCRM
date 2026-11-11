"""Scenario calculator, not measured agency or dry-cleaner economics.

Pass current price hypotheses explicitly. Outputs Markdown to stdout; does not
write raw data or change the canonical price file.
"""
import argparse
import math


def break_even(marketing_cost: float, incremental_margin: float) -> float:
    if marketing_cost < 0 or not 0 < incremental_margin <= 1:
        raise ValueError("Cost must be nonnegative; margin must be in (0, 1].")
    return marketing_cost / incremental_margin


def hours_ceiling(fee, target_contribution, nonlabor, hourly_cost):
    return (fee * (1 - target_contribution) - nonlabor) / hourly_cost


def rub(value):
    return f"{value:,.0f}".replace(",", " ")


def table(headers, rows):
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(x) for x in row) + " |")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fees", nargs=3, type=float, required=True)
    parser.add_argument("--entry", type=float, required=True)
    parser.add_argument("--budget-shares", nargs="+", type=float, required=True)
    parser.add_argument("--launches-per-month", type=int)
    parser.add_argument("--target-new-clients", type=int)
    args = parser.parse_args()
    if min(*args.fees, args.entry) <= 0:
        parser.error("Prices must be positive")
    if any(not 0 < s <= 1 for s in args.budget_shares):
        parser.error("Budget shares must be in (0, 1]")
    if (args.launches_per_month is None) != (args.target_new_clients is None):
        parser.error("Pass both launch rate and target, or neither")
    if args.launches_per_month is not None and min(args.launches_per_month, args.target_new_clients) <= 0:
        parser.error("Launch rate and target must be positive")

    print("SCENARIOS ONLY. Ads=50k, tools=5k, order=2500 are assumptions.\n")
    print("## Client break-even: incremental revenue, not attributed revenue")
    table(["Fee", "All marketing", "Margin 30%", "Margin 40%", "Margin 50%", "Orders at 2500 / margin 40%"],
          [[rub(f), rub(f + 55_000),
            *[rub(break_even(f + 55_000, m)) for m in (.3, .4, .5)],
            math.ceil(break_even(f + 55_000, .4) / 2500)] for f in args.fees])

    print("## Marketing budget remaining after fee")
    table(["Monthly turnover", "Budget share", "Total budget", *[f"After fee {rub(f)}" for f in args.fees]],
          [[rub(r), f"{s:.0%}", rub(r * s), *[rub(r * s - f) for f in args.fees]]
           for r in (2_000_000, 5_000_000, 10_000_000) for s in args.budget_shares])

    print("## Agency capacity at 40% contribution: nonlabor 5k monthly / 2k entry")
    table(["Product fee", "Total cost ceiling", "Labor budget", "Hours at 1000", "Hours at 1500"],
          [[rub(f), rub(f * .6), rub(f * .6 - n),
            f"{hours_ceiling(f, .4, n, 1000):.1f}", f"{hours_ceiling(f, .4, n, 1500):.1f}"]
           for f, n in [(args.entry, 2000), *[(f, 5000) for f in args.fees]]])

    print("## 20 clients, identical fee: revenue / 40% contribution before unallocated costs")
    table(["Fee", "Revenue", "Contribution"], [[rub(f), rub(20*f), rub(20*f*.4)] for f in args.fees])
    print("## Entry + standard continuation, cost ceilings used as scenario costs")
    f = args.fees[1]
    cost = args.entry * .6 + f * .6
    table(["Mechanism", "Cash after both payments", "Cost of both services", "Contribution before CAC"],
          [["Standalone entry", rub(args.entry+f), rub(cost), rub(args.entry+f-cost)],
           ["Full entry credit", rub(f), rub(cost), rub(f-cost)]])
    print("These two services can span >30 days: this is not GP30.")
    if args.launches_per_month is not None:
        months = math.ceil(args.target_new_clients / args.launches_per_month)
        print("\n## Nominal launch batches; no churn, enough sales, no capacity slowdown")
        table(["Month", "New launches", "Cumulative launched"],
              [[i, min(args.launches_per_month, args.target_new_clients - (i-1)*args.launches_per_month),
                min(i*args.launches_per_month, args.target_new_clients)] for i in range(1, months+1)])
        print("Launch count is not simultaneous service capacity or a sales forecast.")


if __name__ == "__main__":
    main()
