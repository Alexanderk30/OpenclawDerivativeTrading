# Knowledge Graph Documentation

## Overview

The OpenClaw Derivative Trading Bot includes a **distributed knowledge graph** that enables multiple trading agents to learn collectively. Every trade contributes to shared intelligence that improves strategy performance over time.

## Why Knowledge Graph?

Traditional trading bots operate in isolation. This system enables:

- **Collective Intelligence**: 10 agents learning together outperform 10 agents learning alone
- **Pattern Recognition**: Automatically identify what works across thousands of trades
- **Continuous Improvement**: Strategies adapt based on accumulated evidence
- **Transparency**: Full audit trail of decisions and learnings

## Architecture

### File-Based Storage

Knowledge is stored as JSON files in `src/knowledge_graph/nodes/`:

```
nodes/
├── trade_outcomes/        # Individual trade results
├── market_patterns/       # Discovered patterns
├── strategy_insights/     # Strategic learnings
└── parameter_tuning/      # Optimized parameters
```

### Node Types

#### 1. Trade Outcome
Captures the complete result of a trade:

```python
{
  "id": "trade_abc123",
  "type": "trade_outcome",
  "created_at": "2026-03-16T14:30:00",
  "agent_id": "my_trading_agent",
  "content": {
    "symbol": "SPY",
    "strategy": "iron_condor",
    "entry_price": 450.0,
    "exit_price": 448.0,
    "contracts": 2,
    "pnl": 340.0,
    "pnl_percent": 0.38,
    "entry_date": "2026-03-15T09:45:00",
    "exit_date": "2026-03-16T14:30:00",
    "hold_days": 1,
    "lessons_learned": [
      "Waited for IV contraction before entry",
      "Could have held for 50% profit target"
    ]
  },
  "confidence": 1.0,
  "evidence_count": 1,
  "tags": ["SPY", "iron_condor", "trade", "win"],
  "related_nodes": ["insight_prev123"],
  "market_context": {
    "vix_level": 18.5,
    "iv_rank": 45,
    "market_trend": "neutral"
  }
}
```

#### 2. Strategy Insight
Share what you've learned about strategy performance:

```python
{
  "id": "insight_xyz789",
  "type": "strategy_insight",
  "content": {
    "strategy": "iron_condor",
    "insight": "IV rank 40-50 provides optimal risk/reward for SPY",
    "supporting_evidence": ["trade_abc123", "trade_def456"],
    "conditions": {
      "iv_rank_min": 40,
      "iv_rank_max": 50,
      "symbol": "SPY"
    }
  },
  "confidence": 0.75,
  "evidence_count": 15
}
```

#### 3. Market Pattern
Document recurring market behaviors:

```python
{
  "id": "pattern_mno456",
  "type": "market_pattern",
  "content": {
    "pattern_name": "High VIX Iron Condor Edge",
    "description": "Iron condors opened when VIX > 25 show higher win rates",
    "observed_count": 23,
    "success_rate": 0.78,
    "symbols": ["SPY", "QQQ"],
    "conditions": {
      "vix_threshold": 25,
      "strategies": ["iron_condor"]
    }
  },
  "confidence": 0.82
}
```

## Usage

### Initialize

```python
from src.knowledge_graph import get_kg

kg = get_kg()
```

### Before Trading

Always query historical performance:

```python
# Get performance summary
perf = kg.get_performance_summary(
    symbol="SPY",
    strategy="iron_condor",
    days=30
)

print(f"Win rate: {perf['win_rate']:.1%}")
print(f"Avg P&L: ${perf['avg_pnl']:.2f}")
print(f"Total trades: {perf['total_trades']}")

# Query relevant insights
insights = kg.query(
    symbol="SPY",
    strategy="iron_condor",
    min_confidence=0.6
)

# Check if we should trade
if perf['win_rate'] < 0.4:
    print("⚠️ Historical win rate is low - consider skipping")
```

### After Trading

Store the outcome:

```python
node_id = kg.store_trade_outcome(
    agent_id="my_agent",
    symbol="SPY",
    strategy="iron_condor",
    entry_price=450.0,
    exit_price=448.0,
    contracts=2,
    pnl=340.0,
    pnl_percent=0.38,
    entry_date="2026-03-15T09:45:00",
    exit_date="2026-03-16T14:30:00",
    market_context={
        "vix_level": 18.5,
        "iv_rank": 45
    },
    lessons_learned=[
        "Good entry timing - waited for IV contraction",
        "Consider holding for 50% profit target next time"
    ]
)
```

### Share Insights

When you discover something important:

```python
kg.store_strategy_insight(
    agent_id="my_agent",
    strategy="iron_condor",
    insight="Wider strike widths (10+ points) work better in high IV",
    supporting_evidence=[trade_node_id],
    confidence=0.7,
    conditions={
        "iv_rank_min": 50,
        "strike_width_min": 10
    }
)
```

## Query System

### Basic Queries

```python
# All trades for a symbol
results = kg.query(symbol="SPY")

# All insights for a strategy
results = kg.query(
    node_type="strategy_insight",
    strategy="iron_condor"
)

# High-confidence recent patterns
results = kg.query(
    node_type="market_pattern",
    since="2026-03-01",
    min_confidence=0.7
)

# Filter by multiple tags
results = kg.query(
    tags=["SPY", "win", "iron_condor"]
)
```

### Graph Traversal

Follow connections between nodes:

```python
# Get related knowledge 2 hops out
related = kg.get_related_knowledge(
    node_id="trade_abc123",
    depth=2
)

# Returns: {0: [start_node], 1: [direct_related], 2: [indirect_related]}
```

## Best Practices

### 1. Always Query Before Trading

```python
def execute_trade(symbol, strategy, signal):
    # Get context
    context = kg.get_performance_summary(symbol, strategy)
    
    # Apply wisdom
    if context['win_rate'] < 0.35:
        return {"status": "skipped", "reason": "poor_historical_performance"}
    
    # Execute...
```

### 2. Always Store After Trading

```python
def on_trade_complete(trade_result):
    # Required: store outcome
    kg.store_trade_outcome(**trade_result)
    
    # Optional: extract and store insights
    if trade_result['pnl'] > expected:
        kg.store_strategy_insight(...)
```

### 3. Be Specific in Lessons

❌ Bad: "Trade went well"
✅ Good: "Entry at 30 delta captured 80% of available premium"

### 4. Link Related Trades

```python
# Reference previous similar trades
kg.store_trade_outcome(
    ...,
    related_nodes=["trade_similar_1", "trade_similar_2"]
)
```

## Indexing

The system maintains a fast lookup index (`index.json`) with:
- **by_symbol**: Quick lookup by ticker
- **by_strategy**: Filter by strategy type
- **by_date**: Temporal queries
- **by_agent**: Track agent contributions
- **by_outcome**: Win/loss analysis

The index auto-updates when you store new nodes.

## Confidence Scoring

Confidence evolves with evidence:

- **Trade Outcomes**: 1.0 (direct observation)
- **Strategy Insights**: Based on supporting evidence count
- **Market Patterns**: `min(observations/10, 1.0)`

Query with `min_confidence` to filter for high-quality knowledge.

## Multi-Agent Coordination

When multiple agents trade:

1. **Agent A** trades SPY, stores outcome
2. **Agent B** queries before trading SPY, learns from A's experience
3. **Agent B** makes better-informed decision
4. **Agent B** stores their outcome
5. **Collective intelligence grows**

## Safety

- **No secrets in graph**: Never store API keys, account info
- **Paper trading enforced**: All trades must be paper until authorized
- **Confidence thresholds**: Filter low-confidence knowledge

## API Reference

### TradingKnowledgeGraph

#### `store_trade_outcome(...)`
Store a completed trade.

**Parameters:**
- `agent_id` (str): Unique agent identifier
- `symbol` (str): Ticker symbol
- `strategy` (str): Strategy name
- `entry_price` (float): Entry price
- `exit_price` (float): Exit price
- `contracts` (int): Number of contracts
- `pnl` (float): Profit/loss in dollars
- `pnl_percent` (float): P&L as percentage
- `entry_date` (str): ISO format entry timestamp
- `exit_date` (str): ISO format exit timestamp
- `market_context` (dict): VIX, IV rank, etc.
- `lessons_learned` (list): String lessons
- `related_nodes` (list): Related node IDs

**Returns:** `str` - Node ID

#### `store_strategy_insight(...)`
Store a strategic discovery.

**Parameters:**
- `agent_id` (str): Agent identifier
- `strategy` (str): Strategy name
- `insight` (str): The insight text
- `supporting_evidence` (list): Trade node IDs
- `confidence` (float): 0.0-1.0
- `conditions` (dict): When this applies
- `related_nodes` (list): Related nodes

**Returns:** `str` - Node ID

#### `query(...)`
Query the knowledge graph.

**Parameters:**
- `symbol` (str): Filter by symbol
- `strategy` (str): Filter by strategy
- `node_type` (str): Filter by type
- `since` (str): ISO date for temporal filter
- `min_confidence` (float): Minimum confidence
- `tags` (list): Required tags

**Returns:** `list` - Matching nodes

#### `get_performance_summary(...)`
Get performance statistics.

**Parameters:**
- `symbol` (str): Symbol to analyze
- `strategy` (str): Strategy to analyze
- `days` (int): Lookback period

**Returns:** `dict` - Performance metrics
