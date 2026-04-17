from typing import Dict, Any


def build_api_connector_payload(name: str, endpoint_url: str, method: str = 'GET') -> Dict[str, Any]:
    return {
        'source': 'rest_api',
        'name': name,
        'endpoint_url': endpoint_url,
        'method': method,
        'status': 'configured',
    }
