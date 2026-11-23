site_configuration = {
    "systems": [
        {
            "name": "iris",
            "descr": "ULHPC Iris cluster)",
            "hostnames": [r"iris-[0-9]{3}"],
            "modules_system": "lmod",
            "partitions": [
                {
                    "name": "batch",
                    "scheduler": "slurm",
                    "launcher": "srun",
                    "access": ["--partition=batch"],
                    "environs": ["testing-foss", "testing-easybuild"],
                }
            ],
        }
    ],
    "environments": [
        {
            "name": "testing-foss",
            "modules": [
                "env/testing/2025a",
                "toolchain/foss/2025a",
            ],
            "env_vars": [
                ["PMIX_MCA_gds", "hash"],
            ],
        },
        {
            "name": "testing-easybuild",
            "modules": [
                "env/testing/2025a",
                "tools/EasyBuild",
            ],
        },
    ],
}
