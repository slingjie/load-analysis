# Copilot Instructions for Load Analysis & Energy Storage Platform

## Project Overview

This is a Vite + React + FastAPI system for analyzing electricity load data and calculating energy storage system sizing and economics. The core domain involves **time-of-use (TOU) tariff scheduling**, **storage cycle accounting**, and **financial feasibility modeling**.

**Key Domains:**
- **Load Analysis**: CSV/Excel upload → 15-min resampling → anomaly detection + quality report
- **TOU Configuration**: Monthly schedule grid + date-rule overrides + 12-month price mappings
- **Storage Cycles**: Charge/discharge window detection → energy accounting → profit calculation per day/month/year
- **Storage Economics**: Cash flow projection → IRR/payback period → feasibility screening

---

## Critical Architecture Patterns

### 1. **Frontend State Management** (`App.tsx`)
- **Single page app** with 9 tabs: editor, price, analysis, matrix, quality, storage, profit, economics, summary
- **State structure**: `currentConfigId` + `lastStorageRun` (holds cleaned load, config snapshot, calculation results)
- **Calculation trigger**: `StorageCyclesPage.tsx` → POST `/api/storage/cycles` → results stored in `lastStorageRun.storageResult`
- **Key pattern**: UI never refetches once computed; results live in React state until user re-runs calculation

### 2. **Backend Service Layers** (`backend/services/`)

| Module | Responsibility |
|--------|-----------------|
| `loader.py` | Parse CSV/Excel → DataFrame with `timestamp(datetime64), load_kw(float)` |
| `cleaning.py` | Detect nulls, zeros, negatives → quality report + cleaned points |
| `cycles.py` | **Core domain**: 15-min load + TOU schedule + storage params → charge/discharge windows → energy balancing → profit per day/month/year |
| `economics.py` | Annual cash flows + decay curves + NPV/IRR/payback calculation |
| `quality.py` | Aggregated anomaly summary (daily/monthly/continuous spans) |

### 3. **Data Flow: Load to Profit**

```
CSV/Excel Upload
  ↓ loader.parse_load_series()
15-min DataFrame (timestamp, load_kw)
  ↓ cleaning.analyze() + POST /api/load/analyze
QualityReport + cleaned_points[]
  ↓ [User configures TOU schedule + prices]
  ↓ POST /api/storage/cycles (payload: cleaned_points, config, storage_params)
StorageCyclesResponse
  ├─ profit_days[] → daily charge/discharge/profit breakdown
  ├─ profit_months[] → monthly aggregates
  ├─ profit_years[] → yearly aggregates
  └─ cycle_summary → total cycles, revenue, cost
```

---

## Project-Specific Conventions

### **TypeScript/React Naming**
- Components: PascalCase, e.g., `StorageCyclesPage.tsx`, `EnergyMatrixTable.tsx`
- Utilities/hooks: camelCase, e.g., `useLoadAnalysis()` 
- Constants: All-caps `TIER_DEFINITIONS`, `OPERATING_LOGIC_MAP` (in `constants.ts`)
- Types: Interfaces prefixed `Backend*` for API contracts, e.g., `BackendStorageProfit`, `BackendStorageCyclesDay`

### **Python/FastAPI Naming**
- Service modules: snake_case, e.g., `cycles.py`, `economics.py`
- Key functions: `compute_*_step15()` for 15-min granularity, `compute_*_summary_*()` for aggregates
- Dataclasses: Used for response schemas (`StorageCyclesResponse`, `EconomicsResult`)
- Exceptions: Custom `CyclesError(ValueError)` for domain validation

### **TOU & Storage Core Concepts**
- **TierId**: `'深'|'谷'|'平'|'峰'|'尖'` (deep/valley/flat/peak/super-peak) → `TIER_DEFINITIONS` in constants
- **OperatingLogicId**: `'待机'|'充'|'放'` (standby/charge/discharge) → defines hour-level action
- **Schedule**: 24-hour array of `{tou: TierId, op: OperatingLogicId}` per month + date-rule overrides
- **Energy formula**: `'physics'` (equation-based, conservative) vs `'sample'` (empirical averages) for cycle counting

### **Profit Calculation: "Step15" Pattern**
- **Problem**: When discharge window contains both peak and super-peak hours, how is energy allocated?
- **Two strategies** (v1.2.0+):
  1. **Sequential (default)**: Time-ordered linear allocation — each 15-min interval gets its own price from TOU schedule; revenue = sum of (discharge_kw × price_per_point). Conservative, preserves original behavior.
  2. **Price-Priority**: Sorts discharge points by price descending, allocates energy to highest-price intervals first (respecting transformer/battery constraints). Optimizes revenue, typically 5-15% improvement.
- **Implementation**: `_allocate_discharge_by_price()` in `cycles.py` (lines ~1571-1640) handles price-based allocation; `compute_profit_summary_step15()` accepts `discharge_strategy` parameter to switch between strategies

---

## Critical Developer Workflows

### **Local Development**
```bash
# Frontend
npm install && npm run dev          # Vite dev server (port 5173)
npm run build                       # TypeScript check + production build

# Backend
python -m venv .venv
.venv\Scripts\activate             # Windows; source .venv/bin/activate on Linux
pip install -r backend/requirements.txt
# Then run: python -m uvicorn backend.app:app --reload --port 8002

# Or use provided script:
.\start-services.ps1               # Windows; starts both frontend + backend
```

### **Key Testing Patterns**
- **No automated test suite** — use manual verification in docs/储能收益与负荷对比功能_测试指引.md
- **Postman/curl**: Validate API responses directly, extract payload for regression
- **Regression baseline**: Test guide line 210–272 contains sample calculations with expected profit values
- **When testing profit**: Verify peak/super-peak allocation makes sense; if results deviate, check `compute_profit_summary_step15()` in `cycles.py`

### **Configuration as Code Pattern**
- **TOU schedule**: `Schedule[][]` (12 months × 24 hours grid) + `DateRule[]` for overrides
- **Prices**: `MonthlyTouPrices` = 12 × `PriceMap` (tier → price)
- **Storage params**: C-rate, efficiency, DoD, reserves, energy formula choice
- All persisted via `/api/storage/config/*` endpoints (create, load, list)

---

## Common Modification Patterns

### **Adding a New Chart Type**
1. Create component in `components/NewChartPage.tsx` (e.g., based on `MonthlyLoadPriceOverlayChart.tsx`)
2. Import in `App.tsx`, add tab entry
3. Wire data from `lastStorageRun` state to component props
4. Use Chart.js + `chartjs-adapter-date-fns` for time axes

### **Extending Profit Calculation**
- **Logic location**: `backend/services/cycles.py` → `compute_profit_summary_step15()` (discharge strategy switching at line ~1700)
- **Price-priority allocation**: `_allocate_discharge_by_price()` function (lines ~1571-1640)
- **Input**: 15-min DataFrame + TOU schedule + storage config
- **Output**: `StorageProfitWithFormulas` (main/physics/sample variants)
- **Key decision point**: Line ~1574 onwards; if you need peak/super-peak prioritization, modify energy allocation before revenue summation

### **Adding Storage Parameters**
1. Update `StorageParamsTemplate` interface in `types.ts`
2. Add to `STORAGE_PARAMS_TEMPLATES[]` in `constants.ts`
3. Update `StorageWindowsRequest` schema in `backend/schemas.py`
4. Modify `compute_*()` functions to use the new param

---

## Integration Points & External Dependencies

| Dependency | Usage | Note |
|------------|-------|------|
| **Chart.js** | Load/profit visualization, time-axis charts | Requires `chartjs-adapter-date-fns` |
| **xlsx** | Excel export (StorageProfitPage, ProjectSummaryPage) | Read entire result object, export as `.xlsx` |
| **FastAPI** | Backend REST API (CORS-enabled) | Proxied via Vite config; see `vite.config.ts` |
| **pandas** | 15-min resampling, time-series aggregation | Central to `cycles.py` and `loader.py` |

### **API Endpoints (Key Routes)**
- `POST /api/load/analyze` → Load cleaning + quality
- `POST /api/storage/cycles` → Storage cycle + profit calculation (multipart: file + JSON params)
- `POST /api/storage/cycles/curves` → Overlay chart data (before/after storage)
- `POST /api/storage/economics` → Cash flow + IRR (newer, separate from cycles)

---

## Security & Configuration

- **API Keys**: `GEMINI_API_KEY`, `DEEPSEEK_API_KEY` in `.env.local` (never commit)
- **Backend URL**: `VITE_BACKEND_BASE_URL` env var; defaults to `http://localhost:8002`
- **TOU Data**: Contains customer operational schedules — sanitize before export/sharing
- **Load Data**: Customer electricity usage — handle as PII; mask in shared reports

---

## When to Consult Project Specs

Before implementing:
- **Ambiguous business logic** → read `docs/储能收益与负荷对比功能 PRD.md`
- **Breaking changes** → follow Change Proposal process in `AGENTS.md`
- **Profit calculation disputes** → refer to `docs/充放电率计算沟通.md` + test guide line 210+
- **New feature requirements** → check `迁移任务方案/` folder for phase-wise roadmap

---

## Quick Reference: Critical Files

| File | Purpose |
|------|---------|
| `App.tsx` | State root, tab routing, calc orchestration |
| `types.ts` | TypeScript interfaces for all API contracts |
| `constants.ts` | TOU tier definitions, operating logic, default prices |
| `backend/app.py` | FastAPI route definitions + request/response handling |
| `backend/services/cycles.py` | **Core domain**: charge/discharge windows, profit accounting (1746 lines) |
| `docs/储能收益与负荷对比功能_测试指引.md` | Regression test baselines + API payload examples |

---

## Summary

This platform is a **domain-driven design** system where storage cycle physics (charge/discharge window detection, energy balancing) is the intellectual core. When modifying profit logic or TOU handling, always verify against regression tests. The frontend is a thin presentation layer over rich backend computation — focus API changes at backend service layer, then wire to UI components.
