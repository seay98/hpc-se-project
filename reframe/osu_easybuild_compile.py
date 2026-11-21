"""Build OMB 7.5 with EasyBuild, then validate MPI latency/bandwidth.

Run from reframe/:
    reframe -C config/aion.py -c osu_easybuild_compile.py -r -v

The shared placement/reference values mirror the already validated generic tests.
This Aion version builds using a project-local EasyConfig (foss/2025a).
"""

import os
from pathlib import Path
import shlex

import reframe as rfm
import reframe.utility.sanity as sn
from reframe.core.builtins import (
    parameter,
    performance_function,
    run_after,
    run_before,
    sanity_function,
)

ROOT = Path(__file__).resolve().parent
EASYCONFIG = "OSU-Micro-Benchmarks-7.5-foss-2025a-project.eb"
OMB_INSTALL_VERSION = "7.5-foss-2025a-project"
MODULES = ["env/testing/2025a", "toolchain/foss/2025a"]

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
AION_PLACEMENTS = {
    "same_numa": ((0, 0, 0), (1, 0, 0)),
    "cross_numa": ((0, 0, 0), (16, 0, 1)),
    "cross_socket": ((0, 0, 0), (64, 1, 4)),
    "inter_node": ((0, 0, 0), (0, 0, 0)),
}
IRIS_PLACEMENTS = {
    "same_numa": ((0, 0, 0), (2, 0, 0)),
    "cross_socket": ((0, 0, 0), (1, 1, 1)),
    "inter_node": ((0, 0, 0), (0, 0, 0)),
}


@rfm.simple_test
class OMBEasyBuildBuild(rfm.CompileOnlyRegressionTest):
    descr = "Build OMB 7.5 using a custom foss/2025a EasyConfig"
    valid_systems = ["aion:batch", 'iris:batch']
    valid_prog_environs = ["builtin"]
    modules = ["env/testing/2025a", "tools/EasyBuild"]
    # Copy the custom EasyConfig into the ReFrame build stage.
    sourcesdir = str(ROOT / "easyconfigs")
    sourcepath = ""
    build_system = "CustomBuild"

    @run_before("compile")
    def configure_build(self):
        # EasyBuild downloads the OMB source when necessary. Keep all outputs
        # in the ReFrame stage directory; never install into central modules.
        config = shlex.quote(EASYCONFIG)
        install = f"eb/software/OSU-Micro-Benchmarks/{OMB_INSTALL_VERSION}"
        binary_dir = f"{install}/libexec/osu-micro-benchmarks/mpi/pt2pt"
        self.build_system.commands = [
            f'test -f {config} || {{ echo "Custom EasyConfig not staged" >&2; exit 1; }}',
            'command -v eb >/dev/null || { echo "Load tools/EasyBuild before running eb" >&2; exit 1; }',
            f"eb {config} --robot --rebuild "
            '--installpath="${PWD}/eb" '
            '--buildpath="${PWD}/eb-build" '
            '--sourcepath="${PWD}/eb-sources" '
            "--parallel=8",
            f"test -x {binary_dir}/osu_latency",
            f"test -x {binary_dir}/osu_bw",
        ]


class _OMBEasyBuildRun(rfm.RunOnlyRegressionTest):
    placement = parameter(list(AION_PLACEMENTS))
    valid_systems = ["aion:batch", "iris:batch"]
    valid_prog_environs = ["builtin"]
    modules = MODULES
    executable = "/bin/true"
    num_tasks = 2
    exclusive_access = True
    time_limit = "30m"

    @run_after("init")
    def add_build_dependency(self):
        self.depends_on("OMBEasyBuildBuild")

    @run_before("setup")
    def configure_allocation(self):
        cluster = self.current_system.name
        self.skip_if(
            cluster == "iris" and self.placement == "cross_numa",
            "Iris has one NUMA domain per socket",
        )
        inter = self.placement == "inter_node"
        cores = {"aion": 128, "iris": 28}[cluster]
        self.num_tasks_per_node = 1 if inter else 2
        self.num_cpus_per_task = cores if inter else cores // 2

    @run_before("run")
    def configure_runtime(self):
        cluster = self.current_system.name
        build = self.getdep("OMBEasyBuildBuild")
        self.executable = os.path.join(
            build.stagedir,
            "eb",
            "software",
            "OSU-Micro-Benchmarks",
            OMB_INSTALL_VERSION,
            "libexec",
            "osu-micro-benchmarks",
            "mpi",
            "pt2pt",
            self.omb_binary,
        )
        if cluster == "iris":
            self.env_vars["PMIX_MCA_gds"] = "hash"

        inter = self.placement == "inter_node"
        if inter:
            self.job.options += ["--nodes=2"]
        (cpu0, socket0, numa0), (cpu1, socket1, numa1) = (
            AION_PLACEMENTS if cluster == "aion" else IRIS_PLACEMENTS
        )[self.placement]
        cpu_map = str(cpu0) if inter else f"{cpu0},{cpu1}"
        self.job.launcher.options += [f"--cpu-bind=verbose,map_cpu:{cpu_map}"]
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

            metric = "latency" if self.omb_binary == "osu_latency" else "bandwidth"
            unit = "us" if metric == "latency" else "MB/s"
            reference = PERFORMANCE_REFERENCES[cluster][self.placement][metric]
            self.reference = {
                f"{cluster}:batch": {
                    metric: (
                        reference,
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
        host0 = sn.extractsingle(rank0, self.stdout, 1)
        host1 = sn.extractsingle(rank1, self.stdout, 1)
        return sn.all(
            [
                sn.assert_eq(self.job.exitcode, 0),
                sn.assert_found(rank0, self.stdout),
                sn.assert_found(rank1, self.stdout),
                (
                    sn.assert_ne(host0, host1)
                    if self.placement == "inter_node"
                    else sn.assert_eq(host0, host1)
                ),
                sn.assert_found(
                    rf"(?m)^\s*{self.message_size}\s+\d+(?:\.\d+)?\s*$",
                    self.stdout,
                ),
            ]
        )


@rfm.simple_test
class OSULatencyEasyBuild(_OMBEasyBuildRun):
    descr = "OMB 7.5 EasyBuild: MPI latency"
    omb_binary = "osu_latency"
    message_size = 8192
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
class OSUBandwidthEasyBuild(_OMBEasyBuildRun):
    descr = "OMB 7.5 EasyBuild: MPI bandwidth"
    omb_binary = "osu_bw"
    message_size = 1048576
    executable_opts = ["-m", "1048576:1048576"]

    @performance_function("MB/s")
    def bandwidth(self):
        return sn.extractsingle(
            r"(?m)^\s*1048576\s+(\d+(?:\.\d+)?)\s*$",
            self.stdout,
            1,
            float,
        )
