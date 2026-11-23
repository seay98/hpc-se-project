"""Iris/Aion OSU Micro-Benchmarks 7.5: existing-module regression tests.

Aion: 8 tests; Iris: 6 applicable tests (cross_numa is skipped).
Run: reframe -C config/aion.py --system aion:batch -c osu_existing_module.py -r
     reframe -C config/iris.py --system iris:batch -c osu_existing_module.py -r
"""

import shlex

import reframe as rfm
import reframe.utility.sanity as sn
from reframe.core.builtins import (
    parameter,
    performance_function,
    run_before,
    sanity_function,
)

PERFORMANCE_REFERENCES = {
    "aion": {
        "same_numa": {"latency": 0.59, "bandwidth": 14858},
        "cross_numa": {"latency": 2.34, "bandwidth": 12098},
        "cross_socket": {"latency": 3.78, "bandwidth": 9870},
        "inter_node": {"latency": 3.89, "bandwidth": 12328},
    },
    "iris": {
        "same_numa": {"latency": 1.81, "bandwidth": 16362},
        "cross_socket": {"latency": 3.64, "bandwidth": 16692},
        "inter_node": {"latency": 4.09, "bandwidth": 12123},
    },
}

PERFORMANCE_TOLERANCE = 0.30

# OS CPU IDs validated against the full Aion hwloc topology.
# Values are the expected (CPU, physical socket, NUMA node) for rank 0 / rank 1.
AION_PLACEMENTS = {
    "same_numa": ((0, 0, 0), (1, 0, 0)),
    "cross_numa": ((0, 0, 0), (16, 0, 1)),
    "cross_socket": ((0, 0, 0), (64, 1, 4)),
    "inter_node": ((0, 0, 0), (0, 0, 0)),
}


# Iris regular CPU node: 2 physical sockets, each one NUMA node, 14 cores.
# OS CPU IDs are interleaved between sockets.
IRIS_PLACEMENTS = {
    "same_numa": ((0, 0, 0), (2, 0, 0)),
    "cross_socket": ((0, 0, 0), (1, 1, 1)),
    "inter_node": ((0, 0, 0), (0, 0, 0)),
}


def placements_for(system):
    return AION_PLACEMENTS if system == "aion" else IRIS_PLACEMENTS


class _OMBExistingModule(rfm.RunOnlyRegressionTest):
    placement = parameter(list(AION_PLACEMENTS))

    valid_systems = ["aion:batch", "iris:batch"]
    valid_prog_environs = ["testing-foss"]
    # Only the OMB module is test-specific; foss is provided by the environment.
    modules = ["perf/OSU-Micro-Benchmarks/7.5-gompi-2025a"]

    num_tasks = 2
    exclusive_access = True
    time_limit = "15m"

    @run_before("setup")
    def configure_allocation(self):
        cluster = self.current_system.name
        self.skip_if(
            cluster == "iris" and self.placement == "cross_numa",
            "Iris has one NUMA node per socket",
        )
        is_inter_node = self.placement == "inter_node"
        cores_per_node = {"aion": 128, "iris": 28}[cluster]
        self.num_tasks_per_node = 1 if is_inter_node else 2
        # Request full node CPU capacity in each srun step to allow map_cpu.
        self.num_cpus_per_task = (
            cores_per_node if is_inter_node else cores_per_node // 2
        )

    @run_before("run")
    def configure_binding(self):
        is_inter_node = self.placement == "inter_node"
        if is_inter_node:
            self.job.options += ["--nodes=2"]

        (cpu0, socket0, numa0), (cpu1, socket1, numa1) = placements_for(
            self.current_system.name
        )[self.placement]
        cpu_map = f"{cpu0}" if is_inter_node else f"{cpu0},{cpu1}"
        self.job.launcher.options += [f"--cpu-bind=verbose,map_cpu:{cpu_map}"]

        # Preflight uses the SAME srun launcher/CPU map as the real OMB run.
        # Any topology mismatch aborts the job before executing OMB.
        checker = r"""
set -euo pipefail
rank="$SLURM_PROCID"
node="$(hostname)"
case "$rank" in
  0) expected_cpu=CPU0; expected_socket=SOCK0; expected_numa=NUMA0 ;;
  1) expected_cpu=CPU1; expected_socket=SOCK1; expected_numa=NUMA1 ;;
  *) echo "BIND_FAIL unexpected rank=$rank" >&2; exit 2 ;;
esac
actual_cpu="$(awk '/^Cpus_allowed_list:/ {print $2}' /proc/self/status)"
if [[ "$actual_cpu" != "$expected_cpu" ]]; then
  echo "BIND_FAIL rank=$rank host=$node expected_cpu=$expected_cpu actual_cpu=$actual_cpu" >&2
  exit 3
fi
location="$(lscpu -p=CPU,SOCKET,NODE | awk -F, -v cpu="$actual_cpu" '$1 == cpu {print $2 "," $3; exit}')"
if [[ "$location" != "$expected_socket,$expected_numa" ]]; then
  echo "BIND_FAIL rank=$rank host=$node cpu=$actual_cpu expected=$expected_socket,$expected_numa actual=$location" >&2
  exit 4
fi
printf 'BIND_OK rank=%s host=%s cpu=%s socket=%s numa=%s\n' \
  "$rank" "$node" "$actual_cpu" "$expected_socket" "$expected_numa"
"""
        for key, value in {
            "CPU0": cpu0,
            "CPU1": cpu1,
            "SOCK0": socket0,
            "SOCK1": socket1,
            "NUMA0": numa0,
            "NUMA1": numa1,
        }.items():
            checker = checker.replace(key, str(value))
        launcher = self.job.launcher.run_command(self.job)
        self.prerun_cmds = [f"{launcher} bash -c {shlex.quote(checker)} || exit 1"]

    @run_before("run")
    def configure_performance_reference(self):
        cluster = self.current_system.name

        metric = "latency" if self.executable == "osu_latency" else "bandwidth"

        unit = "us" if metric == "latency" else "MB/s"

        value = PERFORMANCE_REFERENCES[cluster][self.placement][metric]

        self.reference = {
            f"{cluster}:batch": {
                metric: (
                    value,
                    -PERFORMANCE_TOLERANCE,
                    PERFORMANCE_TOLERANCE,
                    unit,
                )
            }
        }

    @sanity_function
    def validate(self):
        rank0 = r"(?m)^BIND_OK rank=0 host=(\S+) cpu=\d+ socket=\d+ numa=\d+$"
        rank1 = r"(?m)^BIND_OK rank=1 host=(\S+) cpu=\d+ socket=\d+ numa=\d+$"
        hosts0 = sn.extractsingle(rank0, self.stdout, 1)
        hosts1 = sn.extractsingle(rank1, self.stdout, 1)
        return sn.all(
            [
                sn.assert_eq(self.job.exitcode, 0),
                sn.assert_found(rank0, self.stdout),
                sn.assert_found(rank1, self.stdout),
                (
                    sn.assert_ne(hosts0, hosts1)
                    if self.placement == "inter_node"
                    else sn.assert_eq(hosts0, hosts1)
                ),
                sn.assert_found(
                    rf"(?m)^\s*{self.message_size}\s+\d+(?:\.\d+)?\s*$",
                    self.stdout,
                ),
            ]
        )


@rfm.simple_test
class OSULatency(_OMBExistingModule):
    descr = "OMB 7.5 existing module: MPI latency"
    message_size = 8192
    executable = "osu_latency"
    executable_opts = ["-m", "8192:8192"]

    @performance_function("us")
    def latency(self):
        return sn.extractsingle(
            r"(?m)^\s*8192\s+(\d+(?:\.\d+)?)\s*$",
            self.stdout,
            1,
            float,
        )


@rfm.simple_test
class OSUBandwidth(_OMBExistingModule):
    descr = "OMB 7.5 existing module: MPI bandwidth"
    message_size = 1048576
    executable = "osu_bw"
    executable_opts = ["-m", "1048576:1048576"]

    @performance_function("MB/s")
    def bandwidth(self):
        return sn.extractsingle(
            r"(?m)^\s*1048576\s+(\d+(?:\.\d+)?)\s*$",
            self.stdout,
            1,
            float,
        )
