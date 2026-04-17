"""
AI-driven chart recommendation engine v4.
Skills-first: uses Anthropic Agent Skills when available (better quality).
Falls back to system prompt approach if Skills not configured.

Quality improvement with Skills:
  - Chart analysis rules live in a versioned Skill file, not a prompt string
  - Column type reference (COLUMN_TYPES.md) loads on-demand, saving context tokens
  - Chart selection guide (CHART_RULES.md) only loads when generating charts
  - Skills are shared org-wide — one upload, all API calls benefit
  - Easier to iterate: update the SKILL.md file, re-upload, instantly better results
"""
import io
import csv
import json
import logging
import anthropic
from django.conf import settings

from .ai_profile_planner import build_dataset_profile, build_profile_prompt, heuristic_chart_plan
from .chart_validator import validate_chart_configs
from .ai_policy import get_ai_access_context

logger = logging.getLogger(__name__)

# ── System prompt fallback ────────────────────────────────────────────────────
FALLBACK_SYSTEM_PROMPT = """Data viz expert. Analyse sample data + metadata. Output JSON chart specs.

COLUMN TYPES: year=time axis only | month=time axis, sort Jan-Dec | ratio=×100 show as % |
percentage=show as % | metric/currency=numeric KPI | count=integer KPI |
category≤30=dimension | high_card>30=horizontal_bar top20 only | id=never use as axis

RULES (strict):
- year/month: NEVER as KPI or histogram — time axis only
- high_card: horizontal_bar top 20 max, never y-axis
- text/category as y-axis: FORBIDDEN — use a NUMERIC column as y-axis
- For COUNT distributions (gender count, job type count): set x_axis=category_col, y_axis=ANY_numeric_col, aggregation=count. NEVER set y_axis same as x_axis.
- ratio: ×100, label "Col (%)"
- Month+Year both exist: combined_date_key="Month / Year"
- No duplicate chart concepts

CHART TYPES: kpi(3-5 cards) | line(time+metric,size=full) | horizontal_bar(>12 cats,top20) |
doughnut(2-8 cats) | bar(≤12 cats,optional group_by) | scatter(2 numerics) |
heatmap(3+numeric,size=full) | histogram(metric/currency distribution)

Return ONLY valid JSON array, no markdown:
[{"title":"...","chart_type":"bar|horizontal_bar|line|area|scatter|pie|doughnut|histogram|heatmap|kpi",
"x_axis":"col or Month / Year or ''","y_axis":"numeric col or ''","aggregation":"sum|mean|count|min|max",
"group_by":"col or ''","color":"violet|blue|emerald|amber|rose|cyan|multi","size":"sm|md|lg|full",
"x_label":"...","y_label":"...","insight":"one business insight","is_time_series":true,
"combined_date_key":"Month / Year or ''"}]"""


# ── Prompt builders ────────────────────────────────────────────────────────────

# Token budget: keep prompt under this many characters to avoid rate limits
# 25 sample rows is sufficient — column patterns repeat after ~10 rows
MAX_SAMPLE_ROWS = 25
MAX_PROMPT_CHARS = 12_000   # ~3k tokens, well under the 30k/min limit


def _build_sample_csv(analysis_result: dict, max_rows: int = MAX_SAMPLE_ROWS) -> str:
    """Render up to max_rows of preview data as a clean CSV string."""
    preview = analysis_result.get('preview', {})
    columns = preview.get('columns', [])
    rows    = preview.get('rows', [])
    if not columns or not rows:
        return ''
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows[:max_rows]:
        writer.writerow([str(v) if v != '' else '' for v in row])
    return buf.getvalue()


def _build_col_metadata(cols: list, semantic_groups: dict,
                         combined_dates: list, correlation) -> str:
    """Build column metadata section of the prompt."""
    lines = ['COLUMN METADATA:',
             f"{'Column':<30} {'Semantic Type':<14} {'Stats / Top Values'}",
             '-' * 80]

    for c in cols[:40]:
        name = c['name']
        st   = c.get('semantic_type', '?')
        if c.get('is_numeric') or c.get('coerced_numeric'):
            mn  = c.get('mean')
            mn_s = f"{mn:.4f}" if isinstance(mn, float) else str(mn or '?')
            lines.append(
                f"  {name:<28} [{st:<12}]  "
                f"min={c.get('min','?')}  max={c.get('max','?')}  mean={mn_s}"
                f"  null={c.get('null_pct',0)}%"
            )
        else:
            top = [str(tv['value']) for tv in c.get('top_values', [])[:5]]
            lines.append(
                f"  {name:<28} [{st:<12}]  "
                f"{c.get('unique_count','?')} unique  ({', '.join(top)})"
                f"  null={c.get('null_pct',0)}%"
            )

    if semantic_groups:
        lines.append('\nSEMANTIC GROUPS:')
        for grp, col_names in semantic_groups.items():
            if col_names:
                lines.append(f"  {grp:<14}: {', '.join(col_names)}")

    if combined_dates:
        lines.append('\nCOMBINED DATE COLUMNS (use for time series):')
        for combo in combined_dates:
            sample = ', '.join(combo.get('sample', [])[:5])
            lines.append(
                f"  combined_date_key = \"{combo['display_name']}\""
                f"  (from {combo['month_col']} + {combo['year_col']})"
                f"  sample: {sample}"
            )

    if correlation:
        strong = []
        col_names = correlation.get('columns', [])
        matrix    = correlation.get('matrix', [])
        for i in range(len(col_names)):
            for j in range(i + 1, len(col_names)):
                try:
                    v = matrix[i][j]
                    if v is not None and abs(v) >= 0.5:
                        strong.append(f"{col_names[i]} ↔ {col_names[j]} (r={v:.2f})")
                except (IndexError, TypeError):
                    pass
        if strong:
            lines.append('\nNOTABLE CORRELATIONS:')
            for s in strong[:6]:
                lines.append(f"  {s}")

    return '\n'.join(lines)


def _build_user_prompt(analysis_result: dict, filename: str) -> str:
    """Build the user message that contains the actual data."""
    rows_total  = analysis_result.get('rows', 0)
    cols        = analysis_result.get('columns', [])
    sg          = analysis_result.get('semantic_groups', {})
    combos      = analysis_result.get('combined_dates', [])
    corr        = analysis_result.get('correlation')
    sample_csv  = _build_sample_csv(analysis_result, max_rows=MAX_SAMPLE_ROWS)
    sample_rows = len(analysis_result.get('preview', {}).get('rows', []))
    col_meta    = _build_col_metadata(cols, sg, combos, corr)

    small_note = " [SMALL DATASET - note uncertainty]" if rows_total < 30 else ""
    return f"""Dataset: "{filename}" | {rows_total:,} rows | {len(cols)} cols | {sample_rows} sample rows{small_note}

DATA SAMPLE:
{sample_csv}
{col_meta}

Generate insightful charts using the sample values above."""


# ── Main API calls ────────────────────────────────────────────────────────────

def _call_with_skill(client: anthropic.Anthropic, user_prompt: str,
                     skill_id: str) -> str:
    """Call Claude with Agent Skill — higher quality, more efficient."""
    import requests

    payload = {
        'model':      'claude-sonnet-4-20250514',
        'max_tokens': 3000,
        'container': {
            'skills': [{
                'type':     'custom',
                'skill_id': skill_id,
                'version':  'latest',
            }]
        },
        'tools': [{'type': 'code_execution_20250825', 'name': 'code_execution'}],
        'messages': [{'role': 'user', 'content': user_prompt}],
    }

    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key':         settings.ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'anthropic-beta':    'code-execution-2025-08-25,skills-2025-10-02',
            'content-type':      'application/json',
        },
        json=payload,
        timeout=120,
    )

    if not resp.ok:
        if resp.status_code == 429:
            raise anthropic.RateLimitError(
                message=resp.json().get('error',{}).get('message','Rate limit'),
                response=resp, body=resp.json()
            )
        raise RuntimeError(f"Skills API call failed ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()

    # Handle pause_turn (Skills may pause mid-execution)
    max_continuations = 5
    while data.get('stop_reason') == 'pause_turn' and max_continuations > 0:
        container_id = data.get('container', {}).get('id')
        payload_cont = {
            **payload,
            'container': {**payload['container'], 'id': container_id},
            'messages': payload['messages'] + [
                {'role': 'assistant', 'content': data['content']},
                {'role': 'user',      'content': 'continue'},
            ],
        }
        resp = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=resp.request.headers,
            json=payload_cont,
            timeout=120,
        )
        if not resp.ok:
            break
        data = resp.json()
        max_continuations -= 1

    # Extract text from response content blocks
    for block in data.get('content', []):
        if block.get('type') == 'text' and block.get('text', '').strip():
            return block['text']

    raise RuntimeError("No text content in Skills API response")


def _call_with_system_prompt(client: anthropic.Anthropic, user_prompt: str) -> str:
    """Call Claude with inline system prompt — with retry on rate limit."""
    import time

    # Truncate prompt if still too large
    if len(FALLBACK_SYSTEM_PROMPT) + len(user_prompt) > MAX_PROMPT_CHARS:
        # Trim the CSV sample section only, keep metadata
        csv_start = user_prompt.find('ACTUAL SAMPLE DATA:')
        csv_end   = user_prompt.find('─────────', csv_start + 30) if csv_start != -1 else -1
        if csv_start != -1 and csv_end != -1:
            # Replace CSV with a shorter version (10 rows)
            short_csv = _build_sample_csv(
                {'preview': {'columns': [], 'rows': []}}, max_rows=10
            )
            # Just log and continue — the metadata section is still valuable
            logger.warning("Prompt too large, sample already truncated to 25 rows")

    last_err = None
    for attempt in range(3):
        try:
            msg = client.messages.create(
                model='claude-sonnet-4-20250514',
                max_tokens=2500,
                system=FALLBACK_SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': user_prompt}],
            )
            return msg.content[0].text
        except anthropic.RateLimitError as e:
            last_err = e
            wait = (2 ** attempt) * 10   # 10s, 20s, 40s
            logger.warning(f"Rate limit hit (attempt {attempt+1}/3), waiting {wait}s: {e}")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code == 429:
                last_err = e
                wait = (2 ** attempt) * 10
                logger.warning(f"429 rate limit (attempt {attempt+1}/3), waiting {wait}s")
                time.sleep(wait)
            else:
                raise
    raise last_err


def _parse_json_response(raw: str) -> list[dict]:
    """Parse the JSON array from Claude's response."""
    raw = raw.strip()
    if '```' in raw:
        for part in raw.split('```'):
            part = part.strip().lstrip('json').strip()
            if part.startswith('['):
                raw = part
                break
    # Find the JSON array
    start = raw.find('[')
    end   = raw.rfind(']')
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    configs = json.loads(raw)
    if not isinstance(configs, list):
        raise ValueError('Expected JSON array from AI')
    return configs


# ── Public interface ──────────────────────────────────────────────────────────

def ai_recommend_charts(analysis_result: dict, filename: str, user=None) -> list[dict]:
    """
    Generate chart recommendations using a profile-first AI flow.

    New flow:
    1. Build dataset profile in Python
    2. Detect analytical patterns
    3. Ask AI to plan charts from the profile
    4. Validate/repair/reject weak chart specs
    5. Backfill with deterministic charts so paid AI output stays full and useful
    """
    profile = build_dataset_profile(analysis_result, filename)
    user_prompt = build_profile_prompt(profile)
    use_skills = getattr(settings, 'USE_ANTHROPIC_SKILLS', False)
    configs = []

    ai_context = get_ai_access_context(user, feature='chart_generation', estimated_tokens=3500)
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if api_key and ai_context.get('ai_enabled'):
        client = anthropic.Anthropic(api_key=api_key)
        if use_skills:
            skill_id = getattr(settings, 'DATALENS_SKILL_CHART_ANALYSIS', '')
            if not skill_id:
                try:
                    from .skills_manager import get_skill_id
                    skill_id = get_skill_id('chart_analysis') or ''
                except Exception as e:
                    logger.warning(f"Could not load skill ID: {e}")
            if skill_id:
                try:
                    logger.info(f"Using profile-first Agent Skill for chart generation: {skill_id}")
                    raw = _call_with_skill(client, user_prompt, skill_id)
                    configs = _parse_json_response(raw)
                except Exception as e:
                    logger.warning(f"Profile-first Skill call failed, falling back to system prompt: {e}")

        if not configs:
            try:
                logger.info("Using profile-first system prompt for chart generation")
                raw = _call_with_system_prompt(client, user_prompt)
                configs = _parse_json_response(raw)
            except Exception as e:
                logger.warning(f"Profile-first AI planning failed, using heuristic chart plan: {e}")
                configs = []
    else:
        logger.info(f"AI chart planning unavailable ({ai_context.get('reason')}); using heuristic chart plan")

    validated, debug = validate_chart_configs(configs, profile)
    fallback_target = 10
    if len(validated) < fallback_target:
        fallback = heuristic_chart_plan(profile, target_count=fallback_target)
        fallback_validated, fallback_debug = validate_chart_configs(fallback, profile)
        seen = {(c.get('chart_type'), c.get('x_axis'), c.get('y_axis'), c.get('group_by') or '') for c in validated}
        for cfg in fallback_validated:
            key = (cfg.get('chart_type'), cfg.get('x_axis'), cfg.get('y_axis'), cfg.get('group_by') or '')
            if key not in seen:
                validated.append(cfg)
                seen.add(key)
            if len(validated) >= fallback_target:
                break
        debug.extend(fallback_debug)

    profile.setdefault('ai_planning_debug', {})
    profile['ai_planning_debug'] = {
        'profile_summary': {
            'row_count': profile.get('row_count'),
            'column_count': profile.get('column_count'),
            'measures': profile.get('measures'),
            'dimensions': profile.get('dimensions'),
            'time_columns': profile.get('time_columns'),
            'target_columns': profile.get('target_columns'),
            'patterns': (profile.get('pattern_profile') or {}).get('patterns', []),
            'quality_flags': profile.get('quality_flags', []),
        },
        'validated_count': len(validated),
        'ai_mode': 'ai' if ai_context.get('ai_enabled') else 'manual',
        'ai_reason': ai_context.get('reason'),
        'raw_ai_count': len(configs),
        'validation_debug': debug[:40],
    }
    try:
        analysis_result['ai_planning_debug'] = profile['ai_planning_debug']
    except Exception:
        pass
    return validated


def _record_tokens(user, input_tokens: int, output_tokens: int):
    """Record token usage — fails silently so it never blocks chart generation."""
    try:
        from apps.billing.models import TokenUsage
        TokenUsage.record(user, input_tokens, output_tokens)
    except Exception as e:
        logger.debug(f"Token recording failed: {e}")


def ai_generate_insights(upload, analysis_result: dict) -> str:
    """
    Generate business narrative insights using Claude.
    Uses the insights Skill if available, otherwise uses a system prompt.
    """
    client     = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    use_skills = getattr(settings, 'USE_ANTHROPIC_SKILLS', False)
    cols       = analysis_result.get('columns', [])
    rows_total = analysis_result.get('rows', 0)
    sg         = analysis_result.get('semantic_groups', {})

    user_prompt = f"""Dataset: "{upload.original_name}" ({rows_total:,} rows, {len(cols)} columns)

Column summary:
{_build_col_metadata(cols, sg, analysis_result.get('combined_dates',[]), analysis_result.get('correlation'))}

Generate a concise business intelligence report covering:
1. Executive summary (2 sentences)
2. Key metrics with specific numbers
3. Top performers and underperformers (by name)
4. Notable trends or patterns
5. One concrete recommendation

Use markdown. Keep under 400 words. Write for a business manager."""

    if use_skills:
        skill_id = getattr(settings, 'DATALENS_SKILL_INSIGHTS', '')
        if not skill_id:
            try:
                from .skills_manager import get_skill_id
                skill_id = get_skill_id('insights') or ''
            except Exception:
                pass
        if skill_id:
            try:
                return _call_with_skill(client, user_prompt, skill_id)
            except Exception as e:
                logger.warning(f"Insights Skill failed: {e}")

    # Fallback
    msg = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=800,
        system="You are a senior business intelligence analyst. Generate concise, specific insights with real numbers.",
        messages=[{'role': 'user', 'content': user_prompt}],
    )
    return msg.content[0].text


def apply_ai_recommendations(upload, configs: list[dict]) -> list:
    """Turn AI config dicts into ChartConfig DB records with cached data."""
    from .models import ChartConfig
    from .charts import build_chart_data

    upload.chart_configs.filter(is_auto=True).delete()

    VALID_CT    = {ct for ct, _ in ChartConfig.CHART_TYPES}
    VALID_AGG   = {a  for a,  _ in ChartConfig.AGG_CHOICES}
    VALID_COLOR = {c  for c,  _ in ChartConfig.COLOR_PALETTES}
    VALID_SIZE  = {s  for s,  _ in ChartConfig.SIZE_CHOICES}

    created = []
    for i, cfg in enumerate(configs):
        ctype = cfg.get('chart_type', 'bar')
        if ctype not in VALID_CT:
            ctype = 'bar'

        extra = {
            'x_label':           str(cfg.get('x_label', '')),
            'y_label':           str(cfg.get('y_label', '')),
            'insight':           str(cfg.get('insight', '')),
            'is_time_series':    bool(cfg.get('is_time_series', False)),
            'combined_date_key': str(cfg.get('combined_date_key', '')),
        }

        chart = ChartConfig.objects.create(
            upload=upload,
            title=str(cfg.get('title', f'Chart {i+1}'))[:150],
            chart_type=ctype,
            x_axis=str(cfg.get('x_axis', ''))[:255],
            y_axis=str(cfg.get('y_axis', ''))[:255],
            group_by=str(cfg.get('group_by', ''))[:255],
            aggregation=(cfg.get('aggregation', 'mean')
                         if cfg.get('aggregation') in VALID_AGG else 'mean'),
            color=(cfg.get('color', 'violet')
                   if cfg.get('color') in VALID_COLOR else 'violet'),
            size=(cfg.get('size', 'md')
                  if cfg.get('size') in VALID_SIZE else 'md'),
            sort_order=i,
            is_auto=True,
            config_json=extra,
        )

        try:
            chart.cached_data = build_chart_data(upload, chart)
            chart.save(update_fields=['cached_data'])
        except Exception:
            pass

        created.append(chart)

    return created
