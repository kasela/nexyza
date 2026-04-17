"""
AI insights via Anthropic Claude API.
Profile-first to reduce token waste and improve relevance.
"""
import anthropic
from django.conf import settings

from .ai_profile_planner import build_dataset_profile


def _build_insight_prompt(analysis_result: dict, filename: str) -> str:
    profile = build_dataset_profile(analysis_result, filename)
    patterns = (profile.get('pattern_profile') or {}).get('patterns', [])
    opps = (profile.get('pattern_profile') or {}).get('opportunities', [])

    col_lines = []
    for col in profile.get('column_profiles', [])[:25]:
        samples = ', '.join(col.get('sample_values') or [])
        col_lines.append(
            f"- {col['name']} | semantic={col['semantic_type']} | role={col['role']} | "
            f"unique={col['unique_count']} | null={col['null_pct']}% | samples={samples}"
        )

    opp_lines = [f"- {o['intent']} ({o['priority']}): {o['reason']}" for o in opps[:10]]
    return f"""You are a senior business intelligence analyst.
Analyse this DATASET PROFILE, not raw rows.

Dataset: {filename}
Rows: {profile.get('row_count')}
Columns: {profile.get('column_count')}
Measures: {', '.join(profile.get('measures') or [])}
Dimensions: {', '.join(profile.get('dimensions') or [])}
Time columns: {', '.join(profile.get('time_columns') or [])}
Target columns: {', '.join(profile.get('target_columns') or [])}
Patterns detected: {', '.join(patterns) or 'none'}
Quality flags: {', '.join(profile.get('quality_flags') or []) or 'none'}

COLUMN PROFILE:
{chr(10).join(col_lines)}

TOP ANALYTICAL OPPORTUNITIES:
{chr(10).join(opp_lines)}

Write a concise markdown report with:
1. Executive summary (2 short sentences)
2. Strongest analytical opportunities
3. Likely business questions this dataset can answer
4. Recommended chart/analysis focus
5. One practical recommendation
Keep under 350 words.
"""


def generate_insights(analysis_result: dict, filename: str) -> str:
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        profile = build_dataset_profile(analysis_result, filename)
        measures = ', '.join(profile.get('measures')[:4]) or 'no clear measures'
        dims = ', '.join(profile.get('dimensions')[:4]) or 'no clear dimensions'
        patterns = ', '.join((profile.get('pattern_profile') or {}).get('patterns', [])[:5]) or 'limited patterns detected'
        return (
            f"### Executive summary\n"
            f"This dataset contains {profile.get('row_count', 0):,} rows and {profile.get('column_count', 0)} columns. "
            f"Detected measures: {measures}. Detected dimensions: {dims}.\n\n"
            f"### Analytical opportunities\n{patterns}.\n\n"
            f"### Recommendation\nPrioritise trend, ranking, and target-based charts using the highest-confidence fields."
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_insight_prompt(analysis_result, filename)
    msg = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=700,
        system='You write concise, decision-useful business analysis from dataset profiles.',
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text
