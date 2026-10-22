# 🎮 HostCart: Self-Hosted Multi-Media Collection & Analytics Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB.svg?style=flat&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.0+-646CFF.svg?style=flat&logo=vite&logoColor=white)](https://vitejs.dev)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-3.4+-38B2AC.svg?style=flat&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![Test Coverage](https://img.shields.io/badge/Coverage-95.8%25-brightgreen.svg?style=flat)](https://pytest.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

**HostCart** is a modern, self-hosted, unified media tracking and analytics platform designed for collectors and enthusiasts. Take complete ownership of your entertainment history across **Video Games**, **Movies**, **TV Shows**, and **Books**—with zero cloud lock-in, zero subscription fees, and 100% privacy.

Featuring the **Arcadia Dark Obsidian & Crimson** interface, live metadata lookups from industry-standard APIs, one-click progress increments, automated pipeline transitions, and deep media analytics charts.

---

## 🎨 The Arcadia Experience

HostCart is built around the **Arcadia** design system—an obsidian dark palette (`#0b0d12`) accented with vibrant crimson and rose glows (`#e11d48`, `#f43f5e`), glassmorphism card surfaces, and responsive micro-interactions:

* **Hero Showcase Carousel**: Rotates your currently active titles with high-resolution poster art, backlog progress rings, and quick actions.
* **Media Activity Pulse & Curator XP**: Live sidebar telemetry tracking your total library size, completion rate, and curator leveling milestones.
* **Underline-Tabbed Filter Bar**: Seamless switching between **All**, **Games**, **Movies**, **TV Shows**, and **Books**, with status filtering (*Backlog*, *In Progress*, *Completed*, *On Hold*, *Dropped*, *Wishlist*) and multi-parameter sorting.
* **Quick Resume Strip**: Horizontal cards highlighting items you're actively playing, watching, or reading.
* **1-Click Progress Increments**: Dedicated `+1 hr`, `+1 ep`, or `+10 pgs` buttons directly on media cards that automatically advance your progress and auto-transition items to *Completed* when total progress is reached.

---

## 🌟 Key Features

### 1. Multi-Media Universal Catalog
Manage all 4 entertainment pillars in a single database with tailored metrics:
* 🎮 **Video Games**: Track playtime hours, target completion hours, platforms (PC, PS5, Switch, Xbox, Retro), and release years.
* 🎬 **Movies**: Track runtimes, watch counts, release years, directors, and formats (4K UHD, Blu-ray, Digital, Theater).
* 📺 **TV Shows**: Track seasons, total episodes, watched episodes with fast `+1` incrementation, and network/studios.
* 📚 **Books**: Track pages read, page count, authors, ISBNs, and reading formats (Hardcover, Paperback, E-Book, Audiobook).

### 2. Live External Metadata Search
Search external catalogs and import posters, synopses, genres, release dates, and creator details with a single click:
* **IGDB (Twitch API)**: Comprehensive video game catalog with automatic OAuth token generation and renewal.
* **TMDB (The Movie Database)**: Rich metadata and poster art for movies and television series.
* **OpenLibrary & Google Books**: Instant book searches with automatic ISBN and cover resolution (OpenLibrary requires zero API keys).

### 3. Deep Statistics & Media Analytics Engine
Gain actionable insights into your consumption habits via the interactive **Statistics** view:
* **4 Core KPI Cards**: Total Gaming Time (hours), Screen Time (hours), Reading Volume (pages), and Collection Score (weighted completion rating).
* **Monthly Activity Chart**: Grouped bar visualization tracking media completions by category over time.
* **Time Invested Breakdown**: Proportion of entertainment hours dedicated to gaming vs. movies/TV vs. reading.
* **Status Pipeline**: Visual distribution across *Backlog*, *In Progress*, *Completed*, *On Hold*, and *Dropped*.
* **Rating Distribution Histogram**: Frequency analysis of your personal 1–10 scores.
* **Top Genres & Formats Breakdown**: Ranked distribution of your favorite genres and platforms.

### 4. Data Sovereignty & Portability
* **JSON & CSV Export**: Download your complete library or filter by media type with clean timestamps and custom metadata.
* **Robust CSV/JSON Import**: Import existing collections with automated duplicate detection and deduplication.
* **Full User Isolation**: Multi-user support with bcrypt password hashing and JWT token authentication.
* **Settings Management**: Securely configure API keys via the web interface or environment variables with masked secrets.
* **1-Click Demo Seed**: Generate realistic sample media entries across all four media types to test all features instantly.

---

## 🚀 Quick Start with Docker Compose

The easiest way to deploy HostCart is using the official multi-stage Docker container:

### 1. Clone repository & create configuration
```bash
git clone https://github.com/nguyentoanthang/HostCart.git
cd HostCart
cp .env.example .env
```

### 2. Launch with Docker Compose
```bash
docker compose up -d --build
```

### 3. Open in your browser
Navigate to **`http://localhost:8000`** in your browser.
Create an initial account (the first registered account automatically receives Admin privileges) or click **"Load Demo Collection"** in the top navigation to instantly populate your dashboard.

Data is stored persistently in the `./data` directory (`./data/hostcart.db`), and runtime settings are stored in `./config/config.json`.

---

## 🛠️ Local Development Setup

If you wish to develop or modify HostCart locally:

### Prerequisites
* Python 3.12+ (or 3.11+)
* Node.js 20+ and npm
* Git

### Backend Setup (FastAPI + SQLModel)
```bash
# Create and activate a virtual environment
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup (React + Vite + Tailwind CSS)
In a second terminal window:
```bash
cd frontend
npm install
npm run dev
```
The Vite development server runs at `http://localhost:5173` and automatically proxies `/api` calls to the FastAPI server at `http://localhost:8000`.

### Production Build
To test the embedded static production build served by FastAPI:
```bash
cd frontend
npm run build
cd ..
uvicorn src.main:app --host 0.0.0.0 --port 8000
```
FastAPI will serve the compiled React SPA directly from `frontend/dist/` at `http://localhost:8000/`.

---

## ⚙️ Configuration & Environment Variables

HostCart loads configuration from `.env`, environment variables, and `config/config.json` (overridable via the UI Settings panel).

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SECRET_KEY` | `insecure-change-in-production...` | 32+ byte string used to sign JWT authentication tokens. |
| `SERVER_HOST` | `0.0.0.0` | Host IP address to bind uvicorn. |
| `SERVER_PORT` | `8000` | Port to bind uvicorn. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT expiration duration in minutes (1440 = 24 hours). |
| `DATABASE_URL` | `data/hostcart.db` | SQLite database file path. |
| `IGDB_CLIENT_ID` | `""` | Twitch Developer Client ID for video game lookups. |
| `IGDB_CLIENT_SECRET` | `""` | Twitch Developer Client Secret for video game lookups. |
| `TMDB_API_KEY` | `""` | The Movie Database API v3 key for movie & TV lookups. |
| `GOOGLE_BOOKS_API_KEY` | `""` | Optional Google Books API key (fallback for OpenLibrary). |

### Obtaining Free API Keys
* **IGDB**: Create a free developer account at [Twitch Developers Console](https://dev.twitch.tv/console), register an application, and copy your Client ID and Client Secret.
* **TMDB**: Create a free account at [The Movie Database](https://www.themoviedb.org/settings/api) and generate an API key.
* **OpenLibrary / Books**: OpenLibrary works out of the box with zero keys required. If you want additional book cover redundancy, you can generate a free key from the [Google Cloud Console](https://console.cloud.google.com/).

---

## 🧪 Automated Testing & Verification

HostCart comes with a full automated test suite covering authentication, database models, collection CRUD, progress increments, statistics analytics calculations, provider APIs, and CSV/JSON import/export:

```bash
# Run pytest with 90% minimum coverage enforcement
pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=90
```

### Test Coverage Breakdown
```text
Name                          Stmts   Miss  Cover   Missing
-----------------------------------------------------------
src\api\v1\auth.py               72      0   100%
src\api\v1\collection.py        261      3    99%   256, 354-355
src\api\v1\import_export.py      53      4    92%   92, 152-155
src\api\v1\schemas.py           140      0   100%
src\api\v1\search.py             14      0   100%
src\api\v1\settings.py           69      3    96%   68, 86-87
src\core\config.py              157      0   100%
src\core\import_export.py       168     25    85%   
src\core\providers.py           215     19    91%   
src\core\security.py             44      0   100%
src\data\database.py             36      0   100%
src\data\models.py               67      0   100%
src\main.py                      52      3    94%   
-----------------------------------------------------------
TOTAL                          1348     57    96%
Total test coverage: 95.77% (69 passed tests)
```

---

## 📂 Project Architecture

```text
HostCart/
├── .env.example             # Documented template for environment variables
├── .dockerignore            # Build exclusion rules for Docker
├── Dockerfile               # Multi-stage production container build (Node 22 + Python 3.12)
├── docker-compose.yml       # Production container deployment stack
├── requirements.txt         # Production backend dependencies
├── pyproject.toml           # Pytest & tool configurations
├── config/
│   └── config.json          # Default application configuration
├── data/                    # Persistent storage volume (hostcart.db)
├── frontend/                # React + Vite + Tailwind CSS Single Page Application
│   ├── src/
│   │   ├── components/      # UI components (StatisticsView, Modals, Posters, Charts)
│   │   ├── api.js           # Centralized REST client with JWT interceptor
│   │   ├── App.jsx          # Arcadia dashboard shell & collection managers
│   │   └── index.css        # Arcadia dark obsidian theme & CSS variables
│   ├── package.json         # Frontend dependencies & scripts
│   └── vite.config.js       # Vite bundler & reverse proxy configuration
├── src/
│   ├── main.py              # FastAPI application entrypoint & SPA static asset mount
│   ├── api/v1/              # Version 1 API routers (auth, collection, search, stats, impexp)
│   ├── core/                # Core logic (config store, security, providers, import/export)
│   └── data/                # Database engine, session management, and SQLModel schemas
└── tests/                   # End-to-end regression test suites
```

---

## 🤝 Contributing

Contributions, bug reports, and suggestions are warmly welcomed! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before submitting pull requests.

---

## 📜 License

HostCart is open-source software licensed under the [GNU General Public License v3.0](LICENSE).
