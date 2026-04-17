from typing import Dict, Any


def build_excel_online_payload(name: str, workbook_url: str, worksheet: str = '') -> Dict[str, Any]:
    return {
        'source': 'excel_online',
        'name': name,
        'workbook_url': workbook_url,
        'worksheet': worksheet,
        'status': 'ready',
    }
