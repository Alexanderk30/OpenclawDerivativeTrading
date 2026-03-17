"""
Knowledge Graph Client for Trading Agents

Provides file-based knowledge graph capabilities for learning and adaptation.
All trading agents can read/write to build collective intelligence over time.
"""
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any


class TradingKnowledgeGraph:
    """Client for the distributed trading knowledge graph."""
    
    def __init__(self, base_path: str = None):
        if base_path is None:
            # Default to package location
            base_path = Path(__file__).parent
        
        self.base_path = Path(base_path)
        self.nodes_path = self.base_path / "nodes"
        self.index_path = self.base_path / "index.json"
        
        # Ensure directories exist
        self._ensure_structure()
    
    def _ensure_structure(self):
        """Create directory structure if it doesn't exist."""
        for subdir in ["trade_outcomes", "market_patterns", "strategy_insights", "parameter_tuning"]:
            (self.nodes_path / subdir).mkdir(parents=True, exist_ok=True)
    
    def _load_index(self) -> Dict:
        """Load the knowledge graph index."""
        if self.index_path.exists():
            with open(self.index_path, 'r') as f:
                return json.load(f)
        return {"version": "1.0.0", "node_count": 0, "indices": {}}
    
    def _save_index(self, index: Dict):
        """Save the updated index."""
        with open(self.index_path, 'w') as f:
            json.dump(index, f, indent=2)
    
    def store_trade_outcome(self, 
                           agent_id: str,
                           symbol: str,
                           strategy: str,
                           entry_price: float,
                           exit_price: float,
                           contracts: int,
                           pnl: float,
                           pnl_percent: float,
                           entry_date: str,
                           exit_date: str,
                           market_context: Dict = None,
                           lessons_learned: List[str] = None,
                           related_nodes: List[str] = None) -> str:
        """Store a trade outcome node."""
        node_id = f"trade_{uuid.uuid4().hex[:12]}"
        
        node = {
            "id": node_id,
            "type": "trade_outcome",
            "created_at": datetime.now().isoformat(),
            "agent_id": agent_id,
            "content": {
                "symbol": symbol,
                "strategy": strategy,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "contracts": contracts,
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "hold_days": self._calculate_hold_days(entry_date, exit_date),
                "lessons_learned": lessons_learned or []
            },
            "confidence": 1.0,
            "evidence_count": 1,
            "tags": [symbol, strategy, "trade", self._outcome_tag(pnl)],
            "related_nodes": related_nodes or [],
            "market_context": market_context or {}
        }
        
        self._save_node(node, "trade_outcomes")
        self._update_index(node)
        
        return node_id
    
    def store_strategy_insight(self,
                              agent_id: str,
                              strategy: str,
                              insight: str,
                              supporting_evidence: List[str],
                              confidence: float = 0.5,
                              conditions: Dict = None,
                              related_nodes: List[str] = None) -> str:
        """Store a strategic insight."""
        node_id = f"insight_{uuid.uuid4().hex[:12]}"
        
        node = {
            "id": node_id,
            "type": "strategy_insight",
            "created_at": datetime.now().isoformat(),
            "agent_id": agent_id,
            "content": {
                "strategy": strategy,
                "insight": insight,
                "supporting_evidence": supporting_evidence,
                "conditions": conditions or {}
            },
            "confidence": confidence,
            "evidence_count": len(supporting_evidence),
            "tags": [strategy, "insight"],
            "related_nodes": related_nodes or [],
            "market_context": {}
        }
        
        self._save_node(node, "strategy_insights")
        self._update_index(node)
        
        return node_id
    
    def store_market_pattern(self,
                            agent_id: str,
                            pattern_name: str,
                            description: str,
                            observed_count: int,
                            success_rate: float,
                            symbols: List[str],
                            conditions: Dict,
                            related_nodes: List[str] = None) -> str:
        """Store an observed market pattern."""
        node_id = f"pattern_{uuid.uuid4().hex[:12]}"
        
        node = {
            "id": node_id,
            "type": "market_pattern",
            "created_at": datetime.now().isoformat(),
            "agent_id": agent_id,
            "content": {
                "pattern_name": pattern_name,
                "description": description,
                "observed_count": observed_count,
                "success_rate": success_rate,
                "symbols": symbols,
                "conditions": conditions
            },
            "confidence": min(observed_count / 10, 1.0),
            "evidence_count": observed_count,
            "tags": symbols + ["pattern"],
            "related_nodes": related_nodes or [],
            "market_context": conditions.get("market_context", {})
        }
        
        self._save_node(node, "market_patterns")
        self._update_index(node)
        
        return node_id
    
    def query(self, 
             symbol: str = None, 
             strategy: str = None,
             node_type: str = None,
             since: str = None,
             min_confidence: float = 0.0,
             tags: List[str] = None) -> List[Dict]:
        """Query the knowledge graph."""
        results = []
        index = self._load_index()
        
        candidate_ids = set()
        
        if symbol and symbol in index.get("indices", {}).get("by_symbol", {}):
            candidate_ids.update(index["indices"]["by_symbol"][symbol])
        
        if strategy and strategy in index.get("indices", {}).get("by_strategy", {}):
            if candidate_ids:
                candidate_ids &= set(index["indices"]["by_strategy"][strategy])
            else:
                candidate_ids = set(index["indices"]["by_strategy"][strategy])
        
        node_ids = candidate_ids if candidate_ids else self._get_all_node_ids()
        
        for node_id in node_ids:
            node = self._load_node(node_id)
            if not node:
                continue
            
            if node_type and node["type"] != node_type:
                continue
            if node["confidence"] < min_confidence:
                continue
            if tags and not all(tag in node["tags"] for tag in tags):
                continue
            if since and node["created_at"] < since:
                continue
            
            results.append(node)
        
        results.sort(key=lambda x: (x["confidence"], x["created_at"]), reverse=True)
        
        return results
    
    def get_performance_summary(self, symbol: str = None, strategy: str = None, days: int = 30) -> Dict:
        """Get performance statistics from stored trades."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        trades = self.query(node_type="trade_outcome", symbol=symbol, since=since)
        
        if strategy:
            trades = [t for t in trades if t["content"]["strategy"] == strategy]
        
        if not trades:
            return {"total_trades": 0, "win_rate": 0, "avg_pnl": 0}
        
        pnls = [t["content"]["pnl"] for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        
        return {
            "total_trades": len(trades),
            "win_rate": wins / len(trades),
            "avg_pnl": sum(pnls) / len(pnls),
            "total_pnl": sum(pnls),
            "max_win": max(pnls),
            "max_loss": min(pnls),
            "by_strategy": self._aggregate_by_strategy(trades)
        }
    
    def _save_node(self, node: Dict, node_type: str):
        """Save a node to disk."""
        filepath = self.nodes_path / node_type / f"{node['id']}.json"
        with open(filepath, 'w') as f:
            json.dump(node, f, indent=2)
    
    def _load_node(self, node_id: str) -> Optional[Dict]:
        """Load a node by ID."""
        for subdir in ["trade_outcomes", "market_patterns", "strategy_insights", "parameter_tuning"]:
            filepath = self.nodes_path / subdir / f"{node_id}.json"
            if filepath.exists():
                with open(filepath, 'r') as f:
                    return json.load(f)
        return None
    
    def _update_index(self, node: Dict):
        """Update the index with new node information."""
        index = self._load_index()
        
        for key in ["by_symbol", "by_strategy", "by_date", "by_agent", "by_outcome"]:
            if key not in index["indices"]:
                index["indices"][key] = {}
        
        content = node["content"]
        
        if "symbol" in content:
            symbol = content["symbol"]
            if symbol not in index["indices"]["by_symbol"]:
                index["indices"]["by_symbol"][symbol] = []
            index["indices"]["by_symbol"][symbol].append(node["id"])
        
        if "strategy" in content:
            strategy = content["strategy"]
            if strategy not in index["indices"]["by_strategy"]:
                index["indices"]["by_strategy"][strategy] = []
            index["indices"]["by_strategy"][strategy].append(node["id"])
        
        date_key = node["created_at"][:10]
        if date_key not in index["indices"]["by_date"]:
            index["indices"]["by_date"][date_key] = []
        index["indices"]["by_date"][date_key].append(node["id"])
        
        agent = node["agent_id"]
        if agent not in index["indices"]["by_agent"]:
            index["indices"]["by_agent"][agent] = []
        index["indices"]["by_agent"][agent].append(node["id"])
        
        index["node_count"] += 1
        index["last_updated"] = datetime.now().isoformat()
        
        self._save_index(index)
    
    def _get_all_node_ids(self) -> List[str]:
        """Get all node IDs from filesystem."""
        ids = []
        for subdir in self.nodes_path.iterdir():
            if subdir.is_dir():
                for f in subdir.glob("*.json"):
                    ids.append(f.stem)
        return ids
    
    def _calculate_hold_days(self, entry: str, exit: str) -> int:
        """Calculate days held."""
        try:
            entry_dt = datetime.fromisoformat(entry.replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(exit.replace('Z', '+00:00'))
            return (exit_dt - entry_dt).days
        except:
            return 0
    
    def _outcome_tag(self, pnl: float) -> str:
        """Generate outcome tag."""
        if pnl > 0:
            return "win"
        elif pnl < 0:
            return "loss"
        return "breakeven"
    
    def _aggregate_by_strategy(self, trades: List[Dict]) -> Dict:
        """Aggregate performance by strategy."""
        by_strategy = {}
        for trade in trades:
            strategy = trade["content"]["strategy"]
            if strategy not in by_strategy:
                by_strategy[strategy] = {"trades": 0, "wins": 0, "total_pnl": 0}
            
            by_strategy[strategy]["trades"] += 1
            if trade["content"]["pnl"] > 0:
                by_strategy[strategy]["wins"] += 1
            by_strategy[strategy]["total_pnl"] += trade["content"]["pnl"]
        
        for strategy in by_strategy:
            by_strategy[strategy]["win_rate"] = (
                by_strategy[strategy]["wins"] / by_strategy[strategy]["trades"]
            )
        
        return by_strategy


def get_kg() -> TradingKnowledgeGraph:
    """Get a knowledge graph client instance."""
    return TradingKnowledgeGraph()
