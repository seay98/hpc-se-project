# HPC Software Environment — OSU Micro-Benchmarks

ReFrame tests for OSU Micro-Benchmarks (OMB) 7.5 on the ULHPC Aion and Iris clusters.

The **Existing Module** and **Generic Compilation** cases are implemented.

## Directory Structure

```text
hpc-se-project/
├── README.md
└── reframe/
    ├── config/
    │   ├── aion.py             # ReFrame configuration for Aion
    │   └── iris.py             # ReFrame configuration for Iris
    ├── scripts/
    │   └── prepare_omb.py      # Download, verify, cache, and extract OMB sources
    ├── src/                    # OSU source archive cache (created automatically)
    ├── osu_existing_module.py  # OMB tests using the existing module
    └── osu_generic_compile.py  # Build OMB from source and run benchmarks
```

## Prerequisites

- ReFrame model `devel/ReFrame` need to be available on the node, with Lmod and `srun` environment.
- The `env/testing/2025a` module environment. Existing-module tests load
  `perf/OSU-Micro-Benchmarks/7.5-gompi-2025a`; generic compilation loads
  `toolchain/foss/2025a`.
- For generic compilation, write access to `reframe/src/` and network access
  from the build host when the source archive is missing or fails verification.

## Usage

The tests use ReFrame and Slurm to run `osu_latency` and `osu_bw` with different MPI process placements.

Run the following commands from the corresponding cluster's login node.

First, enter the test directory from the repository root:

```bash
cd reframe
```

**Aion:**

```bash
reframe -C config/aion.py --system aion:batch -c osu_existing_module.py -r -v
```

**Iris:**

```bash
reframe -C config/iris.py --system iris:batch -c osu_existing_module.py -r -v
```

To list the available tests without executing them, replace `-r -v` with `-l`.

**Generic compilation:**

```bash
# Aion
reframe -C config/aion.py --system aion:batch -c osu_generic_compile.py -r -v

# Iris
reframe -C config/iris.py --system iris:batch -c osu_generic_compile.py -r -v
```

This case builds OMB 7.5 once per system partition using `toolchain/foss/2025a`
and reuses the build for the latency and bandwidth tests through ReFrame
dependencies. The source archive is verified with SHA-256 and cached as
`reframe/src/osu-micro-benchmarks-7.5.tar.gz`. A missing or invalid archive is
downloaded automatically. Each build extracts a fresh source tree into its
staging directory and installs the binaries under that directory's `osu/` prefix.

ReFrame automatically handles Slurm job submission, CPU binding verification, benchmark execution, and performance extraction.

With the default ReFrame paths and the working directory shown above, staging
files and saved outputs are stored in `reframe/stage/` and `reframe/output/`.

## Test Procedure

**Existing Module (`osu_existing_module.py`):** ReFrame loads the prebuilt
OMB 7.5 module and submits a Slurm job for each benchmark and process placement.
Each job verifies the two ranks' CPU bindings, then runs the module-provided
`osu_latency` or `osu_bw` executable.

**Generic Compilation (`osu_generic_compile.py`):** The `OMBGenericBuild` test
loads the foss toolchain, verifies or downloads the cached source archive, and
extracts it into a fresh staging directory. It runs `./configure` with `mpicc`
and `mpicxx`, builds with `make -j 8`, and installs with `make install` into
the staging directory's `osu/` prefix. The dependent benchmark tests reuse
these binaries and follow the same Slurm allocation and binding checks as the
existing-module tests.

Both implementations run the following measurements for each applicable placement:

- **Latency (`OSULatency` / `OSULatencyGeneric`):** Run
  `osu_latency -m 8192:8192` with two MPI ranks and extract the 8,192-byte
  result in microseconds.
- **Bandwidth (`OSUBandwidth` / `OSUBandwidthGeneric`):** Run
  `osu_bw -m 1048576:1048576` with two MPI ranks and extract the 1 MiB
  result in `MB/s`.

After each run, ReFrame checks the exit code, successful binding checks, expected
same-node or cross-node rank placement, and the benchmark result row. It then
compares the extracted metric against the reference for the cluster and
placement, accepting values within ±30% of that reference.

**EasyBuild Compilation:** Not implemented yet; no test procedure is available.

## Benchmark Coverage

Both implementations use two MPI ranks, exclusive node access, and a 15-minute
job time limit. Latency is measured at 8,192 bytes in microseconds (`us`), and
bandwidth at 1,048,576 bytes in `MB/s`.

| Placement | Description | Aion CPU IDs (rank 0, rank 1) | Iris CPU IDs (rank 0, rank 1) |
| --- | --- | --- | --- |
| `same_numa` | Same node, socket, and NUMA domain | 0, 1 | 0, 2 |
| `cross_numa` | Same node and socket, different NUMA domains | 0, 16 | Skipped |
| `cross_socket` | Same node, different sockets | 0, 64 | 0, 1 |
| `inter_node` | Two nodes, one rank per node | 0 on each node | 0 on each node |

Each implementation runs eight benchmark cases on Aion and six applicable cases
on Iris. Generic compilation also includes a shared build test. Iris has one
NUMA domain per socket, so its `cross_numa` cases are automatically skipped.

Before each benchmark, a preflight step checks the CPU, socket, and NUMA binding
using the same `srun` options as the benchmark. A mismatch aborts the job. Sanity
checks also verify rank placement across hosts and the expected result row.
Both implementations set `PMIX_MCA_gds=hash` on Iris to work around a PMIx
initialization issue.

## Implementation Status

- **Existing Module:** Implemented and tested on Aion and Iris.
- **Generic Compilation:** Implemented and tested on Aion and Iris.
- **EasyBuild Compilation:** Not implemented yet.
