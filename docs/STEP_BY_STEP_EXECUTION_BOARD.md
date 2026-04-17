# Step-by-Step Execution Board

## Step 1
Refactor analyser JavaScript into dedicated static files.

## Step 2
Add smoke tests for upload → analyse → charts → present mode.

## Step 3
Persist chart configuration server-side in `ChartConfig`.

## Step 4
Upgrade report builder and exports.

## Step 5
Strengthen connectors and post-sync automation.

## Step 6
Improve NLQ and AI insight controls.

## Step 7
Complete collaboration, audit, widgets, and embed hardening.


## Completed in the latest build

- Static analyser JS foundation
  - moved analyser state and keyboard enhancements into `static/js/analyser/result-enhancements.js`
  - moved chart gallery builder/filter/sort/layout logic into `static/js/analyser/gallery-page.js`
  - cleaned the malformed `result.html` title block so page metadata stays valid
  - added persistent gallery sort, filter, search, and layout state per upload
  - added gallery summary, empty state, heatmap filter, and auto-chart filter


## Completed in the latest build

- Report builder stabilization bundle
  - moved report builder page logic into `static/js/reportbuilder/builder-page.js`
  - fixed UUID-safe report builder actions and section updates
  - added section summary and last-action status strip
  - added section search/filter on the report canvas
  - added quick section bundles for executive and story flows
  - added local state persistence for report builder selectors and section search


## Completed in the latest build

- Gallery builder correction and persistence bundle
  - corrected gallery preview route to `analyser:preview_chart_data`
  - added builder draft persistence per upload in `static/js/analyser/gallery-page.js`
  - restored builder selections for axis, aggregation, title, labels, insight, and extra measures
  - added regression tests for gallery render and preview endpoint in `apps/analyser/tests.py`


## Latest bundle
- removed duplicate inline analyser enhancement script from `templates/analyser/result.html`
- kept `result-enhancements.js` as the single source of truth for result-page state, shortcuts, chart summary, and presentation presets
- reduced double-binding risk for `showTab`, chart filters, layout actions, and present-mode wrappers


## Latest bundle: result export tools extraction
- moved pin/export/theme-picker helpers from `templates/analyser/result.html` to `static/js/analyser/result-export-tools.js`
- added `result-export-config` JSON bootstrap
- reduced inline JavaScript surface on the analyser result page
- added regression coverage for the static export bundle wiring


## Latest bundle
- moved fullscreen/presentation helper logic from `templates/analyser/result.html` into `static/js/analyser/result-present-mode.js`
- added regression coverage to ensure the result page uses the static present-mode bundle


## Latest bundle
- Extracted analyser collaboration/comment WebSocket logic from `templates/analyser/result.html` into `static/js/analyser/result-collaboration.js`.
- Added JSON config bootstrap for collaboration endpoints and upload ID.


## Latest bundle: shared chart action layer
- extracted shared chart card actions into `static/js/analyser/chart-actions.js`
- wired both result and gallery pages to the same menu/download/copy helpers
- reduced duplicate inline chart action code on the result page
- added regression checks for the shared action bundle


## Latest bundle
- extracted shared chart mutation helpers into `static/js/analyser/chart-mutations.js`
- wired result and gallery pages to a shared UUID-safe chart update config
- removed inline `changeType` / `changeColor` / `changeSize` from `templates/analyser/result.html`


## Latest bundle
- Split gallery builder flow into `gallery-builder-state.js`, `gallery-builder-preview.js`, and `gallery-controls.js` to reduce single-file fragility while preserving the current theme.


- Added modular report builder schedule/state/sections JS bundles and introduced `apps/analyser/chart_services.py` to centralise preview/create/update chart server logic.


- Added report builder export history panel, queue/retry/download endpoints, and a dedicated frontend history module.


## Latest bundle
- added structured chart payload validation in `apps/analyser/chart_services.py`
- preview/create/update chart endpoints now return clearer JSON error payloads with `field_errors`
- gallery builder preview/save flows surface backend validation messages more clearly


- Added report-builder schedule/export validation bundle with service-layer validation and clearer JSON error payloads.
