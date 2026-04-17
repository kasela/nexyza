# Chart Selection Rules

## KPI cards (chart_type: kpi)

**Use for:** ratio, percentage, metric, currency, count columns
**Never use for:** year, month, id, text, boolean, high_cardinality columns
**Size:** sm (fits 3–4 per row in the grid)
**Aggregation:** mean for ratio/percentage, sum for metric/currency/count
**Label format:**
- ratio → "Avg Achievement (%)" with value like "82.5%"
- currency → "Total Revenue" with value like "12.4M"
- count → "Total Staff" with value like "649"

Generate 3–5 KPI cards first — they give immediate summary statistics.

## Time series (chart_type: line or area)

**Use for:** any metric/ratio over time
**Require:** one time column (date, month+year combo, year) + one numeric column
**Sort:** always chronological — Jan→Dec, 2023→2024
**Size:** full (spans full width for readability)
**combined_date_key:** when Month + Year columns both exist, use "Month / Year"
**Label example:** x_label="Period", y_label="Achievement (%)"

## Bar charts (chart_type: bar)

**Use for:** comparing numeric values across categories with ≤12 unique values
**Group by:** add group_by when a secondary categorical variable adds insight
  - e.g., x=Month, y=Achievement, group_by=Category → shows monthly trend by tier
**Never group by:** high_card columns, year columns
**Size:** lg or full for grouped bars

## Horizontal bar (chart_type: horizontal_bar)

**Use for:** ranking categories with many unique values (>12)
**Limit to:** top 20 by value, sorted descending
**Good for:** branch rankings, regional comparisons, manager performance
**Size:** lg or full
**x_label and y_label are swapped** — x_label is the numeric axis, y_label is the category

## Doughnut / pie (chart_type: doughnut or pie)

**Use for:** proportional breakdown of a metric by category
**Only when:** 2–8 unique category values
**Never when:** >8 unique values (use horizontal_bar instead)
**Color:** multi
**Size:** md or lg

## Scatter (chart_type: scatter)

**Use for:** correlation between two numeric columns
**Only valid pairs:** metric vs metric, ratio vs ratio, currency vs count
**Never:** year vs anything, text vs anything
**Size:** md
**insight:** always note the correlation direction and strength

## Histogram (chart_type: histogram)

**Use for:** distribution of a numeric column
**Only valid columns:** metric, currency, count with many unique values (>10)
**Never:** year, month, ratio (use bar instead for ratio)
**Size:** md

## Heatmap (chart_type: heatmap)

**Use for:** correlation matrix when 3+ numeric columns exist
**Size:** full
**insight:** highlight the strongest correlations by name

---

## Priority order for chart generation

1. KPI cards (3–5) — immediate summary
2. Time series — trend over time (if time columns exist)
3. Category ranking — horizontal_bar for the main performance metric by key dimension
4. Distribution by category — doughnut for low-cardinality categories
5. Grouped comparison — bar with group_by for multi-dimensional analysis
6. Scatter — correlation between key metrics
7. Heatmap — if 3+ numeric columns
8. Histograms — distribution shape for key metrics
