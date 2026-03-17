# Setup Instructions

## Prerequisites

- Python 3.9+
- Alpaca Markets account (paper trading recommended)
- Git

## Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd OpenclawDerivativeTrading
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On macOS/Linux
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Create a `.env` file in the project root:

```bash
cp .env.example .env  # If example exists, or create manually
```

Edit `.env` with your credentials:

```env
# Alpaca API (Paper Trading)
ALPACA_API_KEY=your_paper_api_key
ALPACA_SECRET_KEY=your_paper_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Trading Settings
MAX_PORTFOLIO_RISK=0.02
MAX_POSITION_SIZE=0.10
DEFAULT_QUANTITY=1

# Notifications (optional)
ENABLE_NOTIFICATIONS=false
NOTIFICATION_WEBHOOK_URL=

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading.log
```

**Get Alpaca API Keys:**
1. Sign up at https://alpaca.markets
2. Go to Paper Trading dashboard
3. Generate API keys
4. Copy to your `.env` file

### 5. Verify Setup

Run tests to ensure everything is working:

```bash
python -m pytest tests/ -v
```

You should see all tests passing.

### 6. Run Paper Trading

Start with paper trading (simulated money):

```bash
python scripts/paper_trade.py --strategy iron_condor
```

## Configuration

### Strategy Configuration

Edit `config/strategies.yaml` to customize:

```yaml
iron_condor:
  symbols:
    - SPY
    - QQQ
  min_dte: 30
  max_dte: 45
  short_put_delta: -0.15
  short_call_delta: 0.15
```

### Knowledge Graph

The knowledge graph stores learnings in `src/knowledge_graph/nodes/`.
No configuration needed - it works out of the box.

## Going Live (Advanced)

⚠️ **WARNING**: Only proceed after extensive paper trading.

1. Switch to live API keys in `.env`
2. Change `ALPACA_BASE_URL` to live endpoint
3. Set `PAPER_TRADING=false`
4. Run with confirmation prompt:

```bash
python scripts/live_trade.py --strategy iron_condor
```

## Troubleshooting

### Module Not Found

```bash
# Ensure you're in the virtual environment
which python  # Should show venv path

# Reinstall dependencies
pip install -r requirements.txt
```

### Permission Denied (logs/)

```bash
mkdir -p logs
chmod 755 logs
```

### Alpaca Connection Failed

- Verify API keys are correct
- Check you're using paper URL for testing
- Ensure account is approved for trading

## Next Steps

1. Review `docs/STRATEGIES.md` for strategy details
2. Read `docs/KNOWLEDGE_GRAPH.md` for collective learning
3. Check `docs/API.md` for code reference
4. Run backtests before live trading

## Support

Open an issue on GitHub for:
- Bug reports
- Feature requests
- Questions

## Safety Checklist

Before live trading:
- [ ] 30+ days paper trading
- [ ] Understanding of all strategies
- [ ] Risk limits configured
- [ ] Notifications enabled
- [ ] Emergency stop tested
- [ ] Knowledge graph populated with data
