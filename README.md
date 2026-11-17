# HPC Software Environment — OSU Micro-Benchmarks

ReFrame tests for OSU Micro-Benchmarks (OMB) 7.5 on the ULHPC Aion and Iris clusters.

Currently, only the **Existing Module** case is implemented.

## Directory Structure

```text
hpc-se-project/
├── README.md
└── reframe/
    ├── aion.py                 # ReFrame configuration for Aion
    ├── iris.py                 # ReFrame configuration for Iris
    └── osu_existing_module.py  # OMB tests using the existing module
```

## Usage

The tests use ReFrame and Slurm to run `osu_latency` and `osu_bw` with different MPI process placements.

Run the following commands from the corresponding cluster's login node.

First, enter the test directory from the repository root:

```bash
cd reframe
```

**Aion:**

```bash
reframe -C aion.py --system aion:batch \
    -c osu_existing_module.py -r -v
```

**Iris:**

```bash
reframe -C iris.py --system iris:batch \
    -c osu_existing_module.py -r -v
```

To list the available tests without executing them, replace `-r -v` with `-l`.

ReFrame automatically handles Slurm job submission, CPU binding verification, benchmark execution, and performance extraction.

Test outputs are stored in the `stage/` and `output/` directories.

## Implementation Status

- **Existing Module:** Implemented and tested on Aion and Iris.
- **Generic Compilation:** Not implemented yet.
- **EasyBuild Compilation:** Not implemented yet.

Iris does not support the same-socket, cross-NUMA test, so the corresponding cases are automatically skipped.
