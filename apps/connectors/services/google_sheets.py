from typing import Dict, Any


def build_google_sheets_payload(name: str, sheet_url: str, tab: str = '') -> Dict[str, Any]:
    return {
        'source': 'google_sheets',
        'name': name,
        'sheet_url': sheet_url,
        'tab': tab,
        'status': 'ready',
    }
