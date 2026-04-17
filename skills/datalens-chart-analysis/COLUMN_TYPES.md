# Column Type Detection Reference

## Detection algorithm

For each column, check in this order:

### 1. Year
- Numeric, all integers, range 1900–2100, ≤50 unique values
- OR column name contains: year, yr, fy, financial year, fiscal year
- **Treatment:** time axis only. Never histogram. Never KPI. Display as integer.

### 2. Month  
- Numeric 1–12 with ≤12 unique AND name contains: month, mon, mth
- OR string values matching month names (January/Jan/JANUARY)
- **Treatment:** time axis, sort Jan→Dec. Never numeric KPI.
- **Watch out:** "Total Staff" with values 5–15 is NOT a month — check the name.

### 3. Time category (time_cat)
- Strings that are month names or quarter names (Q1/Q2/Q3/Q4)
- **Treatment:** time axis, sort by calendar order.

### 4. Ratio
- Float values between 0.0 and 1.05
- AND name contains: achievement, ratio, rate, pct, percent, coverage, completion,
  attainment, efficiency, utilisation, growth, variance, target
- **Treatment:** ×100 for display, label "Column (%)". Aggregation: mean.
- **Example:** 0.85 → displayed as "85.0%"

### 5. Percentage
- Numeric values 0–105 range
- AND name contains: %, percent, percentage, rate, pct
- OR values were "85%" strings (stripped to 85)
- **Treatment:** display as-is with % suffix. Aggregation: mean.
- **Example:** 85 → displayed as "85.0%"

### 6. Currency
- Mean > 1,000 AND name contains: revenue, sales, income, expense, cost, price,
  value, balance, payment, salary, wage, fee, charge, amount, rent, discount
- **Treatment:** format with k/M suffix. Consider LKR prefix for Sri Lanka datasets.

### 7. Count
- Non-negative integers
- AND name contains: count, qty, quantity, units, number of, num, headcount,
  staff count, employees, seats, transactions, orders, total staff
- **Treatment:** whole numbers, sum aggregation.

### 8. Metric (default numeric)
- Any remaining numeric column
- **Treatment:** standard aggregation, format with k/M for large values.

### 9. Category
- Strings with ≤30 unique values
- Includes: branch, region, province, district, city, town, country, state,
  department, team, manager, staff, employee, category, type, class, product
- **Treatment:** dimension axis for grouping/breakdown.

### 10. High cardinality (high_card)
- Strings with >30 unique values (e.g. Branch with 81 unique values)
- **Treatment:** horizontal_bar ONLY, top 20 by value. Never as y-axis.

### 11. ID / identifier
- Unique or near-unique strings, or name contains: id, code, ref, key, serial
- **Treatment:** NEVER use as chart axis.

---

## Special handling for Sri Lanka business datasets

These column patterns appear frequently in Pilimathalawa / Seetha-style datasets:

| Column name pattern | Likely type | Notes |
|--------------------|-------------|-------|
| Achievement | ratio | Values 0–1, display as % |
| Target | ratio or metric | If 0–1, ratio; if >1, metric |
| Branch | high_card (if 81 unique) | Use horizontal_bar top 20 |
| Province | category (9 unique) | Standard breakdown |
| Category (Gold/Silver/Bronze) | category | Doughnut or grouped bar |
| Regional Manager | category | Bar chart comparison |
| Total Staff | count | NOT a month despite 5–15 values |
| Building Rent | currency | LKR values |
| Total Sq Ft of Showroom | metric | Area measurement |
| Total Given Discount | count or metric | Depends on scale |
