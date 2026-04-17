---
name: datalens-chart-analysis
description: Generate insightful charts, KPIs, and visualisations from tabular
             datasets (CSV/Excel/JSON). Trigger when the user uploads data, asks
             for charts, analysis, insights, dashboards, or visualisations of
             any tabular data. Handles currency, ratios, time series, and
             categorical breakdowns automatically.
---

# Nexyza Chart Analysis

Read COLUMN_TYPES.md first to classify columns, then CHART_RULES.md to select charts.

## Quick column classification

| Pattern | Type | Rule |
|---------|------|------|
| Values 0.0–1.05 + achievement/rate/coverage/efficiency in name | ratio | ×100, label as "Name (%)" |
| Values 0–100 + % in name | percentage | label as "Name (%)" |
| Integers 1900–2100, ≤50 unique | year | time axis only, never KPI |
| Month names (Jan/February...) or integers 1–12 with month in name | month/time_cat | time axis, sort Jan→Dec |
| Mean > 1000 + revenue/sales/amount/rent/cost in name | currency | LKR/$ prefix in label |
| Integers ≥0 + count/staff/qty/employees in name | count | whole numbers only |
| Strings ≤25 unique | category | dimension axis |
| Strings >30 unique | high_card | horizontal_bar top 20 only |
| Full dates (2023-01-15) | date | parse and sort chronologically |

## Critical rules (NEVER break these)

1. **year/month columns** → time axis ONLY — never KPI value, never histogram x-axis
2. **high_card columns** → ONLY in horizontal_bar charts, top 20 max, NEVER as y-axis
3. **text/category as y-axis** → FORBIDDEN — always use numeric column as y-axis
4. **ratio columns** → multiply by 100 for display, label "Column (%)"
5. **Month + Year both present** → combine into time series, use combined_date_key
6. **Month names** → sort Jan→Dec always, NEVER alphabetically
7. **Same concept twice** → NEVER repeat — one trend chart, one branch comparison, etc.

## When Month AND Year columns exist

Use `combined_date_key = "Month / Year"` in the JSON spec.
This creates labels like "Jan 2025", "Feb 2025" sorted chronologically.

## Output — JSON array ONLY, no markdown, no explanation

```json
[{
  "title": "Business-meaningful title",
  "chart_type": "bar|horizontal_bar|line|area|scatter|pie|doughnut|histogram|heatmap|kpi",
  "x_axis": "exact column name or 'Month / Year' or ''",
  "y_axis": "exact numeric column name or ''",
  "aggregation": "sum|mean|count|min|max",
  "group_by": "column name or ''",
  "color": "violet|blue|emerald|amber|rose|cyan|multi",
  "size": "sm|md|lg|full",
  "x_label": "Human-readable X label",
  "y_label": "Human-readable Y label",
  "insight": "One specific business insight this chart reveals",
  "is_time_series": true,
  "combined_date_key": "Month / Year or ''"
}]
```

For full chart selection logic, read CHART_RULES.md.
For complete column type reference, read COLUMN_TYPES.md.
