DataFlow AI — Analytics Overview Rebuild

Included:
- app/dashboard/page.tsx: new dashboard overview with local CSV calculations and inline SVG charts. Basic charting and rule-based insights do not call Groq.
- app/dashboard/workspace/page.tsx: existing dashboard workflow preserved at /dashboard/workspace (upload, inspect, cleaning, AI Analyst, billing).
- app/dashboard/analysis/page.tsx: existing deep-analysis page retained.
- app/layout.tsx: updated browser title/description.

Overview uses the same sessionStorage metadata key and IndexedDB file key as the current workspace so it can restore the latest uploaded CSV in this browser.

Install:
1. Back up frontend/app.
2. Extract ZIP and copy its app folder contents into frontend/app.
3. The existing dashboard page is now moved to app/dashboard/workspace/page.tsx so the new overview can own /dashboard.
4. Restart `npm run dev`.
5. Go to /dashboard. For upload/cleaning, use Datasets in the sidebar; the existing workflow is preserved at /dashboard/workspace.

Notes:
- No new package dependencies.
- Charts and deterministic recommendations on the overview run locally; no Groq calls are made for them.
- Time series is shown only when a valid date field and numeric measure are detected. Category rankings are shown only when compatible columns are detected.
- Inventory recommendations only appear if relevant columns exist. “Fast-moving” is not inferred without movement/sales history.
- This package was generated from the provided ZIP. It has not been tested against your local backend or exact CSV. Please run a local build before deploying.

Patch note:
- Fixed duplicate React keys in the four KPI cards by using a stable label-plus-index key.
- Renamed the preserved workflow page heading to 'Datasets & Data Quality' so it is not presented as a second main dashboard. It remains at /dashboard/workspace and contains the existing upload/cleaning/AI workflow.
