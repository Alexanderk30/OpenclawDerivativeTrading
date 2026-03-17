# OpenClaw Derivative Trading

A multi-agent options trading system built in Python. The system coordinates specialized AI agents through an orchestrator to research opportunities, evaluate risk, generate trade proposals, and execute defined-risk options strategies via the Alpaca API.

## Security Notice

This repository contains no API keys, secrets, or credentials. All sensitive configuration is managed via environment variables or a `.env` file (gitignored). Never commit credentials to version control.

## Architecture

The system is organized around five specialized agents, each with a defined role and communication protocol. The orchestrator routes market triggers to the appropriate agents, enforces safety constraints, and aggregates their outputs into trading decisions.

**Agent pipeline:** Research Agent -> Trading Agent -> Risk Agent -> Execution Engine

- **Orchestrator** -- Central coordinator. Routes triggers, aggregates outputs, enforces global safety. See `agents/orchestrator.md`.
- **Research Agent** -- Market intelligence. Fetches data, calculates indicators (SMA, RSI, IV rank), assesses market regime. See `agents/research_agent.md`.
- **Trading Agent** -- Strategy specialist. Evaluates research against active strategies, generates concrete trade proposals with strikes, expirations, and exit plans. See `agents/trading_agent.md`.
- **Risk Agent** -- Full veto authority. Validates proposals against portfolio constraints, calculates position sizing, enforces exposure limits. See `agents/risk_agent.md`.
- **AI Dev Agent** -- Meta-optimizer. Monitors agent performance, identifies bottlenecks, suggests prompt refinements. See `agents/ai_dev_agent.md`.

## Strategies

**Iron Condor** -- Sells OTM puts and calls with protective wings. Neutral outlook, defined risk, suited to range-bound and low-volatility environments. Four legs per position.

**Credit Spreads** -- Directional spreads (bull put or bear call) with defined risk. Two legs per position. Direction is determined by an adaptive SMA crossover that works with as few as five data points.

**The Wheel** -- Two-phase income strategy. Phase 1 sells cash-secured puts; if assigned, Phase 2 sells covered calls on the acquired shares. Repeats on call-away. Suited to stocks the trader is willing to own long-term.

All strategies are registered centrally in the execution engine. The names `wheel_strategy` and `the_wheel` are interchangeable aliases.

## Risk Management

Risk enforcement is layered across the system and driven by a configurable risk posture defined in `config/risk_posture.json`. Three postures are available (conservative, moderate, aggressive), each with its own limits for per-trade risk, position sizing, daily loss, portfolio heat, correlation exposure, and minimum signal confidence. The active posture defaults to moderate.

Key constraints enforced by the risk manager:

- Per-trade risk capped at a configurable percentage of portfolio value
- Portfolio heat (total open risk) capped at a configurable percentage
- Daily loss limit triggers a halt on new positions
- Per-symbol position count limits
- Minimum signal confidence threshold (signals below are rejected)
- Emergency stop closes all positions via broker

The risk manager reads limits from `risk_posture.json` at initialization and falls back to environment variable defaults in `config/settings.py` if the file is unavailable.

## Collective Knowledge Graph

A file-based distributed knowledge system that enables agents to learn collectively. Every trade outcome, market pattern, strategy insight, and parameter tuning result is stored and indexed for retrieval by any agent.

```python
from src.knowledge_graph import get_kg

kg = get_kg()

# Query historical performance before trading
perf = kg.get_performance_summary(symbol="SPY", strategy="iron_condor")

# Store outcomes after trading
kg.store_trade_outcome(
    agent_id="my_agent",
    symbol="SPY",
    strategy="iron_condor",
    pnl=340.0,
    lessons_learned=["Waited for IV contraction"]
)
```

See `docs/KNOWLEDGE_GRAPH.md` for full documentation.

## Project Structure

```
OpenclawDerivativeTrading/
├── agents/
│   ├── orchestrator.md          # Orchestrator agent spec
│   ├── research_agent.md        # Research agent spec
│   ├── trading_agent.md         # Trading/strategy agent spec
│   ├── risk_agent.md            # Risk agent spec
│   └── ai_dev_agent.md          # Meta-optimizer agent spec
├── config/
│   ├── __init__.py
│   ├── settings.py              # Environment-based configuration
│   ├── strategies.yaml          # Per-strategy parameters
│   └── risk_posture.json        # Risk posture definitions
├── src/
│   ├── main.py                  # CLI entry point
│   ├── broker/
│   │   ├── base_broker.py       # Abstract broker interface
│   │   ├── alpaca_client.py     # Alpaca API client with retry logic
│   │   ├── paper_trading.py     # In-memory paper trading simulator
│   │   ├── ibkr_client.py       # Interactive Brokers client (ib_insync)
│   │   └── broker_factory.py    # Broker factory for multi-broker support
│   ├── strategies/
│   │   ├── base_strategy.py     # Abstract strategy base class
│   │   ├── iron_condor.py       # Iron Condor implementation
│   │   ├── credit_spread.py     # Credit Spread implementation
│   │   └── wheel_strategy.py    # The Wheel implementation
│   ├── risk/
│   │   ├── risk_manager.py      # Portfolio risk management
│   │   └── position_sizer.py    # Position sizing (risk-based, Kelly)
│   ├── execution/
│   │   └── execution_engine.py  # Main trading loop and signal processing
│   ├── knowledge_graph/
│   │   ├── kg_client.py         # Knowledge graph client
│   │   └── index.json           # Fast lookup index
│   ├── data/
│   │   ├── iv_analyzer.py       # IV rank/percentile analysis with caching
│   │   ├── greeks.py            # Black-Scholes Greeks and adjustment recs
│   │   └── ml_signals.py        # ML signal enhancement (GradientBoosting)
│   ├── dashboard/
│   │   └── app.py               # Flask web dashboard with polling API
│   └── utils/
│       ├── logger.py            # Logging configuration
│       └── notifications.py     # Webhook-based alerts
├── scripts/
│   ├── backtest.py              # Strategy backtesting
│   ├── paper_trade.py           # Paper trading runner
│   ├── live_trade.py            # Live trading (with confirmation)
│   ├── dashboard.py             # Standalone dashboard launcher
│   └── heartbeat.sh             # Scheduled health check script
├── tests/
│   ├── test_strategies.py
│   ├── test_risk_management.py
│   ├── test_broker.py
│   └── test_iv_analyzer.py      # Tests for IV, Greeks, ML, Broker Factory, Dashboard
├── docs/
│   ├── SETUP.md
│   ├── STRATEGIES.md
│   └── KNOWLEDGE_GRAPH.md
├── requirements.txt
├── LICENSE
└── .gitignore
```

## Quick Start

### Installation

```bash
git clone https://github.com/Alexanderk30/OpenclawDerivativeTrading.git
cd OpenclawDerivativeTrading

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```bash
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

MAX_PORTFOLIO_RISK=0.02
MAX_POSITION_SIZE=0.10
MAX_DAILY_LOSS=0.05
DEFAULT_QUANTITY=1

ENABLE_NOTIFICATIONS=false
NOTIFICATION_WEBHOOK_URL=

LOG_LEVEL=INFO
LOG_FILE=logs/trading.log
```

Risk posture can be adjusted by changing `active_posture` in `config/risk_posture.json` to `conservative`, `moderate`, or `aggressive`.

### Running

```bash
python -m pytest tests/                                          # Run tests
python scripts/paper_trade.py                                    # Paper trading
python scripts/backtest.py --strategy iron_condor --symbol SPY   # Backtest
python scripts/dashboard.py --port 5000                          # Web dashboard
```

The heartbeat script can be scheduled via cron to run health checks during market hours:

```bash
chmod +x scripts/heartbeat.sh
# Example: run every 5 minutes during market hours
*/5 9-16 * * 1-5 /path/to/scripts/heartbeat.sh
```

## Development

### Adding a New Strategy

1. Create `src/strategies/your_strategy.py` inheriting from `BaseStrategy`.
2. Implement `generate_signals()` and `calculate_position_size()`.
3. Register the strategy in `STRATEGY_REGISTRY` in `src/execution/execution_engine.py`.
4. Add configuration to `config/strategies.yaml`.
5. Add tests in `tests/`.

### Code Quality

```bash
black src/ tests/
flake8 src/ tests/
mypy src/
```

### Testing

```bash
pytest tests/
pytest tests/ --cov=src
pytest tests/test_strategies.py -v
```

## Roadmap

- [x] Knowledge graph for collective agent learning
- [x] Multi-agent orchestration with specialized roles
- [x] Configurable risk postures (conservative / moderate / aggressive)
- [x] IV rank and percentile filtering -- `src/data/iv_analyzer.py`
- [x] Greeks monitoring and position adjustment -- `src/data/greeks.py`
- [x] Web dashboard for monitoring -- `src/dashboard/app.py`
- [x] Machine learning signal enhancement -- `src/data/ml_signals.py`
- [x] Multi-broker support -- `src/broker/broker_factory.py`, `src/broker/ibkr_client.py`

## License

MIT License. See LICENSE file.

## Disclaimer

Trading involves substantial risk of loss. This software is for educational purposes only. Past performance does not guarantee future results. Use paper trading extensively before considering live execution.

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Write tests for new functionality.
4. Submit a pull request.
