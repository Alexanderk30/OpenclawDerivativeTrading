# OpenClaw Derivative Trading Bot

A sophisticated algorithmic trading system for derivatives (options, futures) built with Python.

## 🔒 Security Notice

**IMPORTANT**: This repository contains NO API keys, secrets, or credentials. All sensitive configuration must be managed via environment variables or a secure `.env` file (which is gitignored).

## 📁 Project Structure

```
OpenclawDerivativeTrading/
├── README.md                 # This file
├── .gitignore               # Ensures secrets are never committed
├── requirements.txt         # Python dependencies
├── config/
│   ├── __init__.py
│   ├── settings.py          # Configuration loader (reads from env)
│   └── strategies.yaml      # Strategy configurations
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── broker/
│   │   ├── __init__.py
│   │   ├── alpaca_client.py     # Alpaca API wrapper
│   │   ├── base_broker.py       # Abstract base class
│   │   └── paper_trading.py     # Paper trading simulator
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base_strategy.py     # Abstract strategy base
│   │   ├── iron_condor.py       # Iron Condor options strategy
│   │   ├── credit_spread.py     # Credit spread strategy
│   │   └── wheel_strategy.py    # The Wheel (CSP + CC)
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── position_sizer.py    # Position sizing logic
│   │   ├── risk_manager.py      # Portfolio risk management
│   │   └── max_loss_limits.py   # Loss limit enforcement
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_manager.py     # Order lifecycle management
│   │   └── execution_engine.py  # Trade execution logic
│   ├── data/
│   │   ├── __init__.py
│   │   ├── market_data.py       # Real-time data feed
│   │   └── historical_data.py   # Historical data loader
│   └── utils/
│       ├── __init__.py
│       ├── logger.py            # Logging configuration
│       └── notifications.py     # Alert system
├── tests/
│   ├── __init__.py
│   ├── test_strategies.py
│   ├── test_risk_management.py
│   └── test_broker.py
├── scripts/
│   ├── backtest.py          # Backtesting script
│   ├── paper_trade.py       # Paper trading runner
│   └── live_trade.py        # Live trading (use with caution)
└── docs/
    ├── SETUP.md             # Setup instructions
    ├── STRATEGIES.md        # Strategy documentation
    └── API.md               # API reference
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd OpenclawDerivativeTrading

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the project root (this file is gitignored and never committed):

```bash
# Alpaca API Credentials
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Use paper trading first!

# Trading Configuration
MAX_PORTfolio_RISK=0.02          # Max 2% portfolio risk per trade
MAX_POSITION_SIZE=0.10           # Max 10% in single position
DEFAULT_QUANTITY=1               # Default contract quantity
ENABLE_NOTIFICATIONS=true
NOTIFICATION_WEBHOOK_URL=your_webhook_url

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading.log
```

### 3. Verify Setup

```bash
python -m pytest tests/          # Run tests
python scripts/paper_trade.py    # Start paper trading
```

## 📊 Available Strategies

### Iron Condor
- **Type**: Options (4 legs)
- **Outlook**: Neutral / Range-bound
- **Risk**: Defined (credit received)
- **Use Case**: Low volatility environments

### Credit Spreads
- **Type**: Options (2 legs)
- **Outlook**: Bullish (put spread) or Bearish (call spread)
- **Risk**: Defined (spread width - credit)
- **Use Case**: Directional plays with defined risk

### The Wheel
- **Type**: Options (CSPs + Covered Calls)
- **Outlook**: Bullish long-term
- **Risk**: Assignment risk (stock ownership)
- **Use Case**: Income generation on stocks you want to own

## ⚠️ Risk Management

This bot implements multiple safety layers:

1. **Position Sizing**: Never risk more than configured % per trade
2. **Portfolio Heat**: Total exposure limits
3. **Max Loss Limits**: Automatic position closure at loss thresholds
4. **Paper Trading Mode**: All new strategies run in paper mode first
5. **Kill Switch**: Emergency stop functionality

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src

# Run specific test
pytest tests/test_strategies.py -v
```

## 📈 Backtesting

```bash
python scripts/backtest.py --strategy iron_condor --symbol SPY --days 90
```

## 🔔 Notifications

Configure webhooks for:
- Trade executions
- Risk limit breaches
- Daily P&L summaries
- Error alerts

## 🛠️ Development

### Adding a New Strategy

1. Create `src/strategies/your_strategy.py`
2. Inherit from `BaseStrategy`
3. Implement required methods: `generate_signals()`, `calculate_position_size()`
4. Add tests in `tests/`
5. Update documentation

### Code Style

```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/

# Type check
mypy src/
```

## 📋 TODO

- [ ] Implement IV rank/percentile filtering
- [ ] Add more complex Greeks monitoring
- [ ] Web dashboard for monitoring
- [ ] Machine learning signal enhancement
- [ ] Multi-broker support

## 📜 License

MIT License - See LICENSE file

## ⚡ Disclaimer

**Trading involves substantial risk of loss. This software is for educational purposes only. Past performance does not guarantee future results. Always use paper trading extensively before live trading.**

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## 📞 Support

For issues or questions, please open a GitHub issue.

---

**Remember**: Never commit API keys or secrets to version control!
