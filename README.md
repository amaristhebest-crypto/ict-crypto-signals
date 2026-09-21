# ⚡ ICT Algorithmic Crypto Signals Engine

[![CI](https://github.com/your-username/ict-crypto-signals/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/ict-crypto-signals/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An automated institutional cryptocurrency trading signal scanner built strictly on **Michael J. Huddleston’s Inner Circle Trader (ICT)** and **Smart Money Concepts (SMC)** methodology.

Designed specifically for **Bitcoin (BTC)** and major crypto perpetuals, this engine rejects lagging retail indicators (no RSI, MACD, or Bollinger Bands) and automates price delivery analysis via the **Interbank Price Delivery Algorithm (IPDA)**.

---

## 🏛 Implemented Institutional Footprints

* **Algorithmic Time & Kill Zones (NY Time EST):**
  * Asian Range (20:00 – 00:00 EST)
  * London Open Kill Zone (02:00 – 05:00 EST) — Judas Swing / Manipulation
  * New York Open Kill Zone (07:00 – 10:00 EST) — Macro Catalysts & NYSE Bell (09:30 EST)
  * London Close Kill Zone (10:00 – 12:00 EST)
  * ICT Silver Bullet Windows (10:00 – 11:00 EST & 14:00 – 15:00 EST)
* **True Day Benchmark:**
  * Anchored to the **00:00 NY Midnight Open (NYMO)** (buys below in Discount, sells above in Premium).
* **Liquidity Architecture:**
  * Equal Highs / Lows (EQH / EQL) liquidity pool mapping.
  * Sweep detection: *"Wicks do the damage"* (pierces swing extremes without body acceptance).
* **Displacement & Market Structure Shift (MSS):**
  * *"Bodies tell the story"* (strictly requires candle body closures past key swings with volumetric expansion).
* **PD Array Inventory:**
  * **Fair Value Gaps (FVG)** with exact **Consequent Encroachment (CE - 50% midpoint)** limit entries.
  * **Order Blocks (OB)** with **Mean Threshold (MT - 50% candle body midpoint)** invalidation.
* **SMT Divergence Engine (Smart Money Tool):**
  * Multi-pair correlation scanner (e.g., BTC makes a Lower Low while ETH makes a Higher Low = Institutional Accumulation).
* **Risk & Capital Preservation:**
  * Strict $\ge 2.5\text{R}$ minimum Risk-to-Reward ratio filter.
  * Optimal Trade Entry (OTE: 61.8%, 70.5%, 79.0%) and Fibonacci extensions (-0.27, -0.62, -1.00).
  * Drawdown Rule: Automatically halves trade risk by 50% after 2 consecutive losses.

---

## 📁 Repository Structure

```
ict-crypto-signals/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated GitHub Actions test pipeline
├── src/
│   ├── core/
│   │   ├── models.py            # Typed dataclasses (Candle, FVG, OB, Signal)
│   │   ├── sessions.py          # Kill Zones, NY Midnight Open & True Day
│   │   ├── market_structure.py  # 3-bar swings, sweeps vs MSS body displacement
│   │   ├── pd_arrays.py         # FVGs (CE 50%), Order Blocks (MT 50%), Dealing Range EQ
│   │   ├── smt.py               # ICT SMT Divergence (BTC vs ETH / Correlated pairs)
│   │   └── risk_manager.py      # OTE math, R:R calculation, drawdown halving rules
│   ├── engine/
│   │   ├── detector.py          # Master ICT 2022 Mentorship & Silver Bullet pipeline
│   │   └── fetcher.py           # Public REST data fetcher (ccxt + Binance fallback)
│   ├── alerts/
│   │   ├── telegram.py          # Formatted Telegram bot signal dispatcher
│   │   ├── discord.py           # Rich Discord webhook dispatcher
│   │   └── console.py           # Colorized terminal output
│   └── config/
│       └── settings.py          # YAML & .env configuration loader
├── tests/
│   └── test_ict_engine.py       # Unit tests for all core algorithms
├── config.yaml                  # Asset universe, timeframes, and parameters
├── .env.example                 # Environment variable templates
├── requirements.txt             # Lightweight Python dependencies
├── Dockerfile                   # Docker containerization
├── docker-compose.yml           # 1-click VPS / local service runner
├── main.py                      # Application entry point
└── README.md                    # Institutional documentation
```

---

## 🚀 Quickstart Guide

### 1. Clone & Set Up Locally

```bash
# Clone the repository
git clone https://github.com/your-username/ict-crypto-signals.git
cd ict-crypto-signals

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Alerts (`.env` or `config.yaml`)

Copy the template:
```bash
cp .env.example .env
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
TELEGRAM_CHAT_ID="-1001234567890"
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

*(If tokens are left blank, signals print cleanly to the terminal console).*

### 3. Run Modes

#### A. Deterministic ICT Simulation / Demo
Verify that all algorithms detect the ICT 2022 Mentorship setup with SMT divergence:
```bash
python main.py --mode demo
```

#### B. One-Shot Live Market Scan
Scans BTC/USDT, ETH/USDT, and SOL/USDT once right now:
```bash
python main.py --mode once
```

#### C. Continuous Background Monitoring (Daemon)
Scans live order flow continuously on your chosen interval (default: 60s):
```bash
python main.py --mode run
```

---

## 🐳 Docker Deployment

Run 24/7 in a lightweight background container:

```bash
docker-compose up -d --build
```

Check live logs:
```bash
docker-compose logs -f
```

---

## 📲 Setting Up Telegram Automated Signals

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`, choose a name and username, and copy the **API Token**.
3. Create a channel or group, add your bot as an Admin.
4. Send any message in the group, then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   to find your `chat_id` (e.g. `-100xxxxxxxxxx`).
5. Paste both into `.env`. You will receive real-time alerts formatted with full limit entry, stop loss, and multi-stage target tables.

---

## 🧪 Running Unit Tests

```bash
python -m unittest discover -s tests -v
```

---

## 📤 Pushing to Your GitHub Repository

To push this ready-made project to your own GitHub account:

```bash
# 1. Initialize git
git init -b main

# 2. Stage and commit
git add .
git commit -m "feat: complete ICT/SMC automated crypto signal engine"

# 3. Link your GitHub repository (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/ict-crypto-signals.git

# 4. Push
git push -u origin main
```

---

## ⚠️ Risk Disclaimer

This software is for educational, analytical, and algorithmic research purposes only. Cryptocurrency derivatives involve significant risk. Always validate setups with proper account equity management and backtesting.
