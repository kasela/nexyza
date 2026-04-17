"""
Seed the blog with 6 real, SEO-optimised posts covering Nexyza's main use cases.
Run once: python manage.py seed_blog
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.blog.models import BlogPost

POSTS = [
  {
    'title': 'How to Analyse a CSV File in 60 Seconds — No Code Required',
    'summary': 'Most data analysis tools require SQL, Python, or expensive BI software. Nexyza lets you drag-and-drop any CSV and get instant charts, statistics, and AI insights. Here\'s how.',
    'category': 'tutorial',
    'reading_time': 5,
    'is_featured': True,
    'content': '''<h2>Why Most People Struggle with Data Analysis</h2>
<p>You have a spreadsheet. Maybe it's monthly sales figures, survey responses, or an export from your CRM. You know there are insights hiding in those rows, but extracting them means either learning Python, paying for a BI tool licence, or waiting for a data analyst who has ten other priorities.</p>
<p>Nexyza solves this. Upload any CSV, Excel, or JSON file and you'll have interactive charts, statistical summaries, and AI-generated insights within a minute — no code, no installation, no waiting.</p>

<h2>Step 1: Upload Your File</h2>
<p>From the dashboard, click <strong>Analyse New File</strong> or drag your file directly onto the upload zone. Nexyza accepts:</p>
<ul>
  <li>CSV files (comma, semicolon, or tab separated)</li>
  <li>Excel files (.xlsx and .xls)</li>
  <li>JSON files (array of objects)</li>
</ul>
<p>Files up to 2 MB are supported on the free plan. Paid plans support up to 100 MB.</p>

<h2>Step 2: Review Your Instant Analysis</h2>
<p>Within seconds you'll see:</p>
<ul>
  <li><strong>Column statistics</strong> — mean, median, min, max, null percentage, and unique values for every column</li>
  <li><strong>Distribution histograms</strong> — visual shape of each numeric column</li>
  <li><strong>Correlation matrix</strong> — which columns are related to each other</li>
  <li><strong>Data preview</strong> — the first rows of your file with formatting</li>
</ul>

<h2>Step 3: Generate Charts</h2>
<p>Click <strong>Chart Gallery</strong> to see automatically generated visualisations. Nexyza creates bar charts, line charts, and distributions based on your data's shape. You can customise any chart, add your own, or use the <strong>AI chart builder</strong> to describe what you want in plain English.</p>

<h2>Step 4: Ask Questions in Plain English</h2>
<p>The <strong>Ask AI</strong> tab lets you query your data conversationally. Try questions like:</p>
<ul>
  <li>"Which branch had the highest average sales last quarter?"</li>
  <li>"Show me the top 10 products by revenue"</li>
  <li>"Is there a correlation between marketing spend and new signups?"</li>
</ul>
<p>Nexyza runs the query against your actual data and returns a chart or answer.</p>

<h2>Step 5: Export or Share</h2>
<p>Export your analysis as a PDF report, Excel workbook, or PowerPoint presentation — ready to send to stakeholders. Or generate a read-only share link that anyone can view without an account.</p>

<h2>Start Analysing for Free</h2>
<p>The free plan gives you 5 uploads per month with full analysis, charts, and CSV/JSON export. No credit card required.</p>''',
  },
  {
    'title': 'What is Data Anomaly Detection? A Plain-English Guide',
    'summary': 'Data anomalies are hidden problems that corrupt your analysis — outliers, sudden spikes, missing values, and more. This guide explains what they are, why they matter, and how to find them automatically.',
    'category': 'analytics',
    'reading_time': 6,
    'is_featured': True,
    'content': '''<h2>What Is a Data Anomaly?</h2>
<p>An anomaly is any data point that doesn't fit the expected pattern. In practice, this shows up as:</p>
<ul>
  <li><strong>Outliers</strong> — a sales figure of $980,000 when every other row is between $5,000 and $50,000</li>
  <li><strong>Null spikes</strong> — a column that suddenly has 40% missing values in one week's data</li>
  <li><strong>Constant columns</strong> — a column where every row has the same value, suggesting a data pipeline problem</li>
  <li><strong>Unexpected distributions</strong> — a column that should be normally distributed but has a suspicious cluster at round numbers</li>
</ul>

<h2>Why Anomalies Matter</h2>
<p>If you analyse data without checking for anomalies first, your conclusions may be wrong. A single outlier can shift a mean dramatically. A batch of missing values can make a trend look inverted. Many business decisions made on "data" are actually made on corrupted data.</p>

<h2>The Two Main Detection Methods</h2>
<h3>Z-Score (Standard Deviation)</h3>
<p>The Z-score measures how many standard deviations a value is from the mean. A Z-score above 3 or below -3 typically indicates an outlier. This works well for roughly normal distributions.</p>

<h3>IQR (Interquartile Range)</h3>
<p>The IQR method looks at the middle 50% of your data and flags anything that falls far outside that range. It's more robust than Z-score for skewed distributions.</p>

<h2>How Nexyza Does It</h2>
<p>Nexyza runs both methods simultaneously on every numeric column. From any analysis page, click <strong>🔍 Anomaly</strong> to get:</p>
<ul>
  <li>A severity-ranked list of anomalies (high / medium / low)</li>
  <li>The specific rows and values that triggered each flag</li>
  <li>An AI narrative explaining what the anomalies suggest and how to handle them</li>
</ul>
<p>Pro users also get detection of null spikes, constant columns, and suspected ID columns (columns that look numeric but are actually identifiers).</p>

<h2>What to Do When You Find Anomalies</h2>
<p>Not all anomalies are errors. Some are genuine insights. The right response depends on context:</p>
<ul>
  <li><strong>Outliers</strong> — verify the source. Was the data entered correctly? If so, consider whether to include or exclude them from analysis.</li>
  <li><strong>Null spikes</strong> — investigate your data pipeline. A sudden increase in missing values often signals a collection or import error.</li>
  <li><strong>Constant columns</strong> — these usually indicate a default value or a broken feed. They add no analytical value and should typically be excluded.</li>
</ul>''',
  },
  {
    'title': '5 Ways to Use Live Data Connectors for Real-Time Dashboards',
    'summary': 'Manually exporting and re-uploading data every week kills productivity. Live connectors pull fresh data automatically — here are five practical ways to use them.',
    'category': 'tips',
    'reading_time': 7,
    'is_featured': True,
    'content': '''<h2>The Problem with Manual Data Exports</h2>
<p>Most analytics workflows look like this: export data from system A, open Excel, clean it, re-upload to your analytics tool, regenerate charts, share a PDF. Then do it all again next week.</p>
<p>Live connectors break this cycle. Connect Nexyza directly to your Google Sheet or Excel Online file, and it pulls fresh data automatically on your chosen schedule — every hour, daily, or weekly.</p>

<h2>1. Sales Performance Dashboard</h2>
<p>Keep a Google Sheet that your CRM exports to automatically (most CRMs support this). Connect it to Nexyza with an hourly refresh. Your team gets a live sales dashboard without anyone having to manually update it.</p>

<h2>2. Inventory Tracking</h2>
<p>If your warehouse or e-commerce platform exports stock levels to a Google Sheet, connect it to Nexyza for a daily inventory analysis. Nexyza will automatically flag anomalies — like a product dropping to zero stock — so you can act before it becomes a problem.</p>

<h2>3. Marketing Campaign Monitoring</h2>
<p>Many marketing platforms (Google Ads, Meta, Mailchimp) can export campaign data to Google Sheets via integrations like Zapier or Make. Connect that sheet to Nexyza and you'll have a fresh campaign performance analysis every morning.</p>

<h2>4. Financial Reporting</h2>
<p>Finance teams often maintain a master Excel file in OneDrive or SharePoint. Connect it to Nexyza via the Excel Online connector. When the finance team updates the file, Nexyza re-analyses it automatically — no PDF exports, no manual charting.</p>

<h2>5. Operations Metrics</h2>
<p>Whether it's delivery times, support ticket volumes, or production output — if someone is already keeping a spreadsheet, you can turn it into a live operational dashboard in minutes.</p>

<h2>How to Set Up a Connector</h2>
<ol>
  <li>Go to <strong>Live Connectors</strong> in the sidebar</li>
  <li>Click <strong>Connect Google Sheets</strong> and sign in with your Google account (read-only access)</li>
  <li>Paste the sharing URL of your sheet</li>
  <li>Choose a refresh interval (hourly, 6 hours, daily, or manual)</li>
  <li>Nexyza creates a <strong>[Live]</strong> analysis that updates automatically</li>
</ol>
<p>The Excel Online connector works the same way — just click <strong>Connect Microsoft Excel Online</strong> and sign in with your Microsoft account.</p>''',
  },
  {
    'title': 'How to Build a Data Report That Actually Gets Read',
    'summary': 'Most data reports are ignored because they\'re too long, too technical, and structured for the analyst rather than the reader. Here\'s a framework for building reports that drive decisions.',
    'category': 'tips',
    'reading_time': 6,
    'content': '''<h2>Why Most Data Reports Fail</h2>
<p>The typical data report contains everything the analyst found interesting. Twenty pages of tables, charts, methodology notes, and caveats. By page three, your audience has stopped reading.</p>
<p>A report that drives decisions answers one question on the first page: <em>what should we do?</em></p>

<h2>The Three-Section Structure That Works</h2>
<h3>1. Executive Summary (one page)</h3>
<p>State the key finding and recommendation up front. Don't make the reader scroll to find it. If they read nothing else, they should understand the main message.</p>

<h3>2. Supporting Evidence (two to four pages)</h3>
<p>Three to five charts that directly support your recommendation. Each chart needs a one-sentence title that states the conclusion, not just the topic. "Revenue is up 23% month-on-month" is better than "Monthly Revenue."</p>

<h3>3. Appendix</h3>
<p>All the detail, methodology, and data tables. This satisfies the data-literate reader without cluttering the main report.</p>

<h2>Chart Selection Rules</h2>
<ul>
  <li><strong>Comparisons across categories</strong> → bar chart</li>
  <li><strong>Trends over time</strong> → line chart</li>
  <li><strong>Part-to-whole relationships</strong> → pie or doughnut (only when categories are fewer than 6)</li>
  <li><strong>Correlations</strong> → scatter plot</li>
  <li><strong>Single key metric</strong> → KPI card</li>
</ul>

<h2>Building the Report in Nexyza</h2>
<p>Nexyza's Report Builder lets you drag in sections — headings, text, charts from your gallery, statistics, and AI insights. You can:</p>
<ul>
  <li>Export as a branded PDF with one click</li>
  <li>Generate a public share link for stakeholders who don't have a Nexyza account</li>
  <li>Schedule the report to be emailed automatically every week or month</li>
</ul>
<p>The best reports are the ones that write themselves. Set up a scheduled report with a live connector, and your stakeholders receive an up-to-date analysis in their inbox automatically.</p>''',
  },
  {
    'title': 'Understanding AI Tokens: How Nexyza\'s AI Budget Works',
    'summary': 'Plus and Pro plans include a monthly AI token budget for chart generation, insights, and natural language queries. This guide explains what counts as a token and how to get the most from your budget.',
    'category': 'product',
    'reading_time': 4,
    'content': '''<h2>What Is an AI Token?</h2>
<p>When you use any AI feature in Nexyza — generating a chart, getting AI insights on your data, or asking a natural language question — the request is processed by an AI language model (Anthropic's Claude). That model charges for usage in "tokens," which are roughly chunks of text (about 0.75 words per token).</p>

<h2>How Many Tokens Do Features Use?</h2>
<ul>
  <li><strong>AI chart generation</strong> — 1,500–3,000 tokens per chart</li>
  <li><strong>AI insights</strong> — 2,000–5,000 tokens depending on dataset size</li>
  <li><strong>Natural language query (NLQ)</strong> — 1,000–3,000 tokens per question</li>
  <li><strong>Anomaly narrative</strong> — 1,500–2,500 tokens</li>
  <li><strong>Forecast narrative</strong> — 1,000–2,000 tokens</li>
</ul>

<h2>Plan Budgets</h2>
<ul>
  <li><strong>Free</strong> — no AI features</li>
  <li><strong>Plus</strong> — 200,000 tokens/month (~80–130 AI chart generations)</li>
  <li><strong>Pro</strong> — 2,000,000 tokens/month (~800–1,300 AI chart generations)</li>
</ul>
<p>Your token budget resets on the 1st of every month. Unused tokens do not roll over.</p>

<h2>Checking Your Usage</h2>
<p>You can see your current month's usage at any time from <strong>Settings → AI Usage</strong> or from your dashboard's token usage bar (visible on Plus and Pro plans).</p>

<h2>Tips to Stretch Your Budget</h2>
<ul>
  <li>Generate AI insights once per dataset, then reference the saved insights rather than regenerating them</li>
  <li>Use manual chart creation (rule-based, free) for straightforward charts, and save AI generation for complex or exploratory analysis</li>
  <li>NLQ queries on smaller datasets use fewer tokens — filter your data before querying if possible</li>
</ul>''',
  },
  {
    'title': 'CSV vs Excel vs JSON: Which Format Should You Use for Data Analysis?',
    'summary': 'Each file format has strengths and weaknesses for analysis. This guide helps you choose the right format — and how to convert between them without losing data.',
    'category': 'analytics',
    'reading_time': 5,
    'content': '''<h2>CSV: The Universal Standard</h2>
<p>Comma-separated values files are the most portable data format in existence. Almost every system that stores or exports data can produce a CSV. They're plain text, human-readable, and work everywhere.</p>
<p><strong>Use CSV when:</strong> you're exporting from a database, CRM, or analytics platform; sharing data between different tools; or working with very large files (CSVs are compact).</p>
<p><strong>Limitations:</strong> no data types (everything is text until parsed), no multiple sheets, no formatting, no formulas.</p>

<h2>Excel (.xlsx): The Business Standard</h2>
<p>Excel files are what most business users actually work with. They support multiple sheets, data types, cell formatting, formulas, and charts. The .xlsx format (not the older .xls) is the current standard.</p>
<p><strong>Use Excel when:</strong> your data is already in a spreadsheet with multiple sheets; you need to preserve data types (dates, currencies); or you're sharing with stakeholders who expect an Excel file.</p>
<p><strong>Limitations:</strong> larger file sizes, occasional encoding issues, formulas don't transfer to analysis tools.</p>
<p><strong>Nexyza tip:</strong> when you upload a multi-sheet Excel file, Nexyza shows a sheet selector so you can choose which tab to analyse.</p>

<h2>JSON: The Developer Format</h2>
<p>JSON (JavaScript Object Notation) is the standard for data in web APIs and modern applications. It supports nested data structures that CSV cannot represent.</p>
<p><strong>Use JSON when:</strong> your data comes from an API; you have nested or hierarchical data; or you're a developer working with web application data.</p>
<p><strong>Limitations:</strong> not human-friendly to read, overkill for flat tabular data, larger files than CSV for the same data.</p>
<p><strong>Nexyza tip:</strong> Nexyza expects JSON files to be an array of objects — each object is a row, each key is a column name.</p>

<h2>Converting Between Formats</h2>
<p>Nexyza can export your analysis data in any format regardless of what you uploaded. Use the <strong>Export</strong> dropdown on any result page to download as CSV, JSON, Excel, PDF, or PowerPoint.</p>

<h2>Which Format Should You Upload to Nexyza?</h2>
<p>For most analysis tasks, CSV is the best choice — it's fast to parse, universally compatible, and produces consistent results. If your data has multiple related sheets that you want to explore separately, Excel is better. Use JSON only if your data is already in that format from an API.</p>''',
  },
]


class Command(BaseCommand):
    help = 'Seed the blog with initial posts'

    def handle(self, *args, **options):
        created = 0
        for p in POSTS:
            if BlogPost.objects.filter(title=p['title']).exists():
                self.stdout.write(f"  skip (exists): {p['title'][:50]}")
                continue
            from django.utils import timezone
            from datetime import timedelta
            import random
            post = BlogPost.objects.create(
                title        = p['title'],
                summary      = p['summary'],
                content      = p['content'],
                category     = p['category'],
                reading_time = p['reading_time'],
                is_featured  = p.get('is_featured', False),
                is_published = True,
                author_name  = 'Nexyza Team',
                published_at = timezone.now() - timedelta(days=random.randint(1, 60)),
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(f"  created: {post.title[:60]}"))
        self.stdout.write(self.style.SUCCESS(f"\n✅ {created} posts created"))
