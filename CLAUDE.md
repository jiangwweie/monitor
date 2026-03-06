# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Run backend (FastAPI + uvicorn on port 8000)
python main.py

# Run with virtual environment
source venv/bin/activate && python main.py
```

### Frontend (`web_ui/`)
```bash
cd web_ui
npm install        # Install dependencies
npm run dev        # Dev server on port 5173
npm run build      # TypeScript check + Vite build
npm run lint       # ESLint
npm run preview    # Preview production build
```

### Docker (full stack)
```bash
# 确保宿主机目录存在
mkdir -p /Users/jiangwei/Documents/docker/monitor/{data,logs,config}

# 构建并启动
docker-compose up --build -d

# 查看日志
docker logs -f cryptoradar-backend
docker logs -f cryptoradar-frontend

# 停止
docker-compose down
```
Backend → port 8000, Frontend → port 5174 (Docker).
本地开发：Frontend → port 5173.
所有数据持久化到 `/Users/jiangwei/Documents/docker/monitor/`:
- `data/radar.db` - SQLite 数据库
- `logs/backend.log` - 应用日志
- `config/` - 配置文件导入/导出
- `.env` - 环境变量

## Architecture

The system follows **Clean Architecture / DDD** — dependencies always point inward (infrastructure → application → domain → core).

```
core/           # Innermost layer: entities, interfaces (abstract base classes), exceptions
domain/         # Business logic — no I/O
  strategy/     #   pinbar.py (signal detection), indicators.py, scoring.py
  risk/         #   sizer.py (position sizing)
application/    # Orchestration — wires domain + infrastructure
  monitor_engine.py   # CryptoRadarEngine: main async loop (fetch → detect → score → persist → notify)
  history_scanner.py  # Batch historical signal scan
  chart_service.py    # OHLCV aggregation for chart API
infrastructure/ # External adapters — implement core interfaces
  feed/         #   binance_ws.py (WebSocket K-line stream), binance_kline_fetcher.py (REST)
  reader/       #   binance_api.py (account/position reader, read-only)
  repo/         #   sqlite_repo.py (aiosqlite — signals, secrets/config, positions)
  notify/       #   feishu.py, wecom.py, telegram.py, broadcaster.py
  utils/
web/            # FastAPI routes (api.py) — reads state from app.state injected at startup
web_ui/         # React 19 + TypeScript SPA (single App.tsx, Shadcn UI components)
main.py         # Entrypoint: dependency injection, FastAPI lifespan, uvicorn
```

### Key Architectural Points

**Dependency Injection via `main.py` lifespan**: All components are manually instantiated in `assemble_engine()` and wired together. The `CryptoRadarEngine` and service objects are attached to `app.state` so `web/api.py` routes can access them via `request.app.state`.

**Config persistence in SQLite**: User configuration (Binance API keys, active symbols, monitor intervals, scoring weights, Pinbar thresholds) is stored as key-value secrets in the SQLite DB via `repo.get_secret()` / `repo.set_secret()`. At startup, `main.py` reads these to override defaults.

**Multi-timeframe (MTF) filtering**: The engine monitors multiple intervals simultaneously (15m, 1h, 4h). Each `IntervalConfig` optionally enables a trend filter that requires a lower timeframe signal to align with the higher timeframe trend before passing.

**Zero Execution Policy**: `auto_order_status` is hardcoded `OFF`. The system is strictly read-only — it detects signals and notifies, but never places orders.

**Frontend ↔ Backend**: The React SPA communicates with the FastAPI backend via REST (`/api/...`) and WebSocket (`/ws`). In dev mode, Vite proxies API calls to `localhost:8000`. In production (Docker), Nginx serves the built static files and proxies `/api` to the backend container.

**Frontend structure**: Component-based architecture with feature modules:
- `App.tsx` - Main orchestration: data fetching, state management, tab routing
- `Dashboard.tsx` - System health, API weight, account overview, real-time prices
- `SignalRadar.tsx` - Signal table with filtering, sorting, bulk actions, history scan
- `Positions.tsx` - Active positions grid cards
- `Settings.tsx` - Configuration forms (exchange, pinbar, risk, scoring, notifications)
- `PositionDetailModal.tsx` - Position detail dialog
- `SignalChartModal.tsx` - K-line chart visualization (uses lightweight-charts v5)
- Shadcn UI primitives in `components/ui/`
