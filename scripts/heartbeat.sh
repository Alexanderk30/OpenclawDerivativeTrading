#!/bin/bash
# Trading System Heartbeat Script
# Orchestrator pulse - scheduled check-ins during market hours

set -euo pipefail

WORKSPACE="/Users/clawd/.openclaw/workspace"
LOG_FILE="$WORKSPACE/logs/trading_heartbeat.log"
ORCHESTRATOR_CHANNEL="discord://orchestrator"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if market is open (9:30 AM - 4:00 PM ET, Mon-Fri)
is_market_open() {
    local hour=$(date +%H)
    local min=$(date +%M)
    local dow=$(date +%u)  # 1=Mon, 5=Fri
    
    # Weekend check
    if [ "$dow" -gt 5 ]; then
        return 1
    fi
    
    # Time check (simple version, assumes ET)
    local current_minutes=$((10#$hour * 60 + 10#$min))
    local open_minutes=$((9 * 60 + 30))
    local close_minutes=$((16 * 60))
    
    if [ "$current_minutes" -ge "$open_minutes" ] && [ "$current_minutes" -lt "$close_minutes" ]; then
        return 0
    fi
    
    return 1
}

# Run orchestrator health check
run_health_check() {
    log "Running orchestrator health check..."
    
    # Check if knowledge graph is accessible
    if [ -d "$WORKSPACE/trading_agents/knowledge_graph" ]; then
        log "✓ Knowledge graph accessible"
        NODE_COUNT=$(find "$WORKSPACE/trading_agents/knowledge_graph/nodes" -name "*.json" 2>/dev/null | wc -l)
        log "  Nodes: $NODE_COUNT"
    else
        log "✗ Knowledge graph not found"
        return 1
    fi
    
    # Check agent status (would query Discord/status files in production)
    log "✓ Agent status check placeholder"
    
    # Check daily P&L limits
    log "✓ Risk posture check placeholder"
    
    return 0
}

# Trigger scheduled workflows
trigger_scheduled() {
    log "Checking scheduled workflows..."
    
    # Pre-market check (9:25 AM)
    local hour=$(date +%H)
    local min=$(date +%M)
    
    if [ "$hour" -eq 9 ] && [ "$min" -eq 25 ]; then
        log "Triggering pre-market checks"
        # Would send message to orchestrator channel
        echo "PRE_MARKET_CHECK: Verify agents online, check connectivity" >> "$LOG_FILE"
    fi
    
    # Mid-session check (every hour on the hour)
    if [ "$min" -eq 0 ]; then
        log "Triggering hourly status check"
        echo "HOURLY_CHECK: Quick status update" >> "$LOG_FILE"
    fi
    
    # Pre-close check (3:30 PM)
    if [ "$hour" -eq 15 ] && [ "$min" -eq 30 ]; then
        log "Triggering pre-close reconciliation"
        echo "PRE_CLOSE: Position reconciliation check" >> "$LOG_FILE"
    fi
}

# Main execution
main() {
    log "=== Trading Heartbeat Started ==="
    
    if is_market_open; then
        log "Market is OPEN"
        
        if run_health_check; then
            log "✓ Health check passed"
            trigger_scheduled
        else
            log "✗ Health check failed - alerting"
            # Would send critical alert to Discord
        fi
    else
        log "Market is CLOSED - skipping checks"
    fi
    
    log "=== Heartbeat Complete ==="
    echo "" >> "$LOG_FILE"
}

# Run main
main "$@"
