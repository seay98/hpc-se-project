site_configuration = {
    'systems': [
        {
            'name': 'aion',
            'descr': 'ULHPC Aion cluster',
            'hostnames': [r'aion-[0-9]{4}'],
            'modules_system': 'lmod',
            'partitions': [
                {
                    'name': 'batch',
                    'descr': 'Aion compute nodes',
                    'scheduler': 'slurm',
                    'launcher': 'srun',
                    'access': ['--partition=batch'],
                    'environs': ['builtin'],
                }
            ],
        }
    ]
}

