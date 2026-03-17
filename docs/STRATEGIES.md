# Trading Strategies

## Available Strategies

### 1. Iron Condor

**Type**: Options (4 legs)
**Outlook**: Neutral / Range-bound
**Risk**: Defined (credit received)

#### Structure
- Sell OTM Put (bullish side)
- Buy further OTM Put (protection)
- Sell OTM Call (bearish side)  
- Buy further OTM Call (protection)

#### When to Use
- Low volatility environments
- Range-bound markets
- High IV rank (collect premium)

#### Configuration
```yaml
iron_condor:
  symbols: [SPY, QQQ, IWM]
  min_dte: 30
  max_dte: 45
  short_put_delta: -0.15
  short_call_delta: 0.15
  spread_width: 5.0
  min_credit_ratio: 0.30
  profit_target: 0.50
  stop_loss: 2.00
```

#### Risk/Reward
- **Max Profit**: Credit received
- **Max Loss**: Spread width - credit
- **Breakeven**: Short strikes ± credit

---

### 2. Credit Spreads

**Type**: Options (2 legs)
**Outlook**: Directional (bullish or bearish)
**Risk**: Defined

#### Bull Put Spread
- Sell OTM Put
- Buy further OTM Put

#### Bear Call Spread  
- Sell OTM Call
- Buy further OTM Call

#### When to Use
- Directional conviction
- Defined risk preference
- Income generation

#### Configuration
```yaml
credit_spread:
  symbols: [SPY, QQQ, AAPL, TSLA]
  min_dte: 21
  max_dte: 45
  put_spread_delta: -0.20
  call_spread_delta: 0.20
  spread_width: 5.0
```

#### Risk/Reward
- **Max Profit**: Credit received
- **Max Loss**: Spread width - credit

---

### 3. The Wheel

**Type**: Options (CSPs + Covered Calls)
**Outlook**: Bullish long-term
**Risk**: Assignment (stock ownership)

#### Phase 1: Cash Secured Puts
- Sell CSPs on stocks you want to own
- Collect premium while waiting

#### Phase 2: Covered Calls
- After assignment, sell calls
- Generate income on position
- Repeat until called away

#### When to Use
- Stocks you want to own
- Income generation
- Long-term bullish

#### Configuration
```yaml
wheel_strategy:
  symbols: [AAPL, MSFT, JPM]
  csp_delta: -0.30
  cc_delta: 0.30
  csp_dte: 30
  cc_dte: 30
  max_allocation_per_stock: 0.10
```

#### Risk/Reward
- **Assignment Risk**: Own stock at strike price
- **Premium Income**: Continuous cash flow
- **Opportunity Cost**: Missing moonshots

---

## Strategy Selection

### Market Regime Guide

| Market Condition | Recommended Strategy |
|-----------------|---------------------|
| High IV, Range-bound | Iron Condor |
| High IV, Bullish | Bull Put Spread |
| High IV, Bearish | Bear Call Spread |
| Low IV, Bullish | The Wheel (CSP) |
| Earnings week | Avoid / Reduce size |
| Trending strongly | Directional spreads |

### IV Rank Guidelines

- **IV Rank < 20**: Avoid selling premium (buy instead)
- **IV Rank 20-40**: Small positions, tight spreads
- **IV Rank 40-60**: Optimal for most strategies
- **IV Rank > 60**: Larger positions acceptable, higher risk

## Adding Custom Strategies

1. Create file in `src/strategies/`
2. Inherit from `BaseStrategy`
3. Implement required methods
4. Add configuration to `config/strategies.yaml`
5. Write tests

Example:
```python
from .base_strategy import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    def generate_signals(self, data):
        # Your logic here
        return [Signal(...)]
    
    def calculate_position_size(self, account_value, signal):
        # Sizing logic
        return size
```

## Backtesting

Test strategies before live trading:

```bash
python scripts/backtest.py --strategy iron_condor --symbol SPY --days 90
```

## Knowledge Graph Integration

All strategies benefit from collective learning:

```python
# Query historical performance
perf = kg.get_performance_summary(
    symbol="SPY",
    strategy="iron_condor"
)

# Adjust based on win rate
if perf['win_rate'] < 0.4:
    print("Strategy underperforming - skipping")
```

## Risk Management

Every strategy implements:
- Position sizing limits
- Portfolio heat monitoring
- Max loss thresholds
- Automatic stop losses

See `src/risk/` for implementation details.
