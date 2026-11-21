site_configuration = {
    'systems': [
        {
            'name': 'iris',
            'descr': 'ULHPC Iris cluster)',
            'hostnames': [r'iris-[0-9]{3}'],
            'modules_system': 'lmod',
            'partitions': [
                {
                    'name': 'batch',
                    'scheduler': 'slurm',
                    'launcher': 'srun',
                    'access': ['--partition=batch'],
                    'environs': ['builtin'],
                }
            ],
        }
    ]
}
