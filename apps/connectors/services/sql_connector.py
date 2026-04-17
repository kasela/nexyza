from typing import Dict, Any


def build_sql_connector_payload(name: str, engine: str, host: str, database: str, query: str = '') -> Dict[str, Any]:
    return {
        'source': engine,
        'name': name,
        'host': host,
        'database': database,
        'query': query,
        'status': 'configured',
    }
