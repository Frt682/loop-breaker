"""
Master All-in-One Test Runner for Cursor IDE.
Executes literally every test, matrix permutation, deep rollback,
100-trajectory benchmark, and chart generation in sequence.
"""
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def banner(title: str):
    print("\n" + "=" * 80)
    print(f"  >>> {title.upper()} <<<")
    print("=" * 80)

def main():
    start_total = time.time()
    banner("STEP 1: RUNNING ALL 34 UNIT, MATRIX & PERFORMANCE TESTS")
    subprocess.run("python -m unittest discover -s tests -v", shell=True)

    banner("STEP 2: RUNNING 100-TRAJECTORY EMPIRICAL BENCHMARK (GROUND TRUTH)")
    subprocess.run("python benchmark_100_trajectories.py", shell=True)

    banner("STEP 3: RUNNING INTERACTIVE REALISTIC AGENT SIMULATION SCENARIOS")
    subprocess.run("python simulate_agents.py", shell=True)

    banner("STEP 4: GENERATING GRAPHICAL BENCHMARK CHARTS & VISUAL DASHBOARD")
    subprocess.run("python generate_benchmark_charts.py", shell=True)

    banner("STEP 5: GENERATING OFFICIAL CURSOR AUDIT REPORT")
    subprocess.run("python cursor_verify.py", shell=True)

    elapsed = time.time() - start_total
    print("\n" + "=" * 80)
    print(f"  ALL TEST SUITES COMPLETED IN {elapsed:.2f} SECONDS!")
    print("=" * 80)

if __name__ == "__main__":
    main()
