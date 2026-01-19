# config.py - Configuration for different TNGIS environments

TNGIS_CONFIG = {
    'production': {
        'base_url': 'https://tngis.tn.gov.in',
        'ec_endpoint': '/api/ec/download',
        'auth_required': False,
        'timeout': 30
    },
    'staging': {
        'base_url': 'https://staging-tngis.tn.gov.in',
        'ec_endpoint': '/api/ec/download',
        'auth_required': False,
        'timeout': 30
    }
    # Add other environments as needed
}