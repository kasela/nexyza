---
name: datalens-insights
description: Generate business intelligence narratives and data insights from
             analysed datasets. Trigger when asked for AI insights, data
             summaries, business observations, anomaly explanations, or
             written analysis of a dataset's findings.
---

# Nexyza Business Insights

Generate concise, actionable business insights from dataset analysis results.

## Insight structure

Always produce insights in this order:
1. **Executive Summary** — 2 sentences: what the data covers and the headline finding
2. **Key Metrics** — 3–5 bullet points with specific numbers
3. **Top Performers** — best branches/regions/categories with values
4. **Areas of Concern** — underperformers or anomalies worth investigating
5. **Trend** — directional observation if time data exists
6. **Recommendation** — one concrete, actionable suggestion

## Quality rules

- Use actual numbers from the data, never vague language
- Compare to averages: "Branch X at 93% — 11 points above the 82% network average"
- Name specific entities: "Fernando R manages the lowest-achieving region at 71%"
- Flag data quality: high null %, suspicious values, very small sample sizes
- Keep recommendations specific: "Focus training resources on Bronze 1 branches in Northern Province" not "improve performance"

## Format

Use markdown with clear headings. Keep total response under 400 words.
Write for a business manager, not a data scientist.
