# Initial Position Strategy Configuration

## Overview

The Grid Trading Bot now includes a new configuration option called `initial_position_strategy` that controls how the bot handles sell orders when it doesn't have any shares in stock.

## Problem Solved

Previously, the bot would place sell orders immediately upon startup, even when it had zero shares in stock. This could lead to:
- Rejected orders (trying to sell shares you don't own)
- Margin calls or short positions (if broker allows)
- Unintended trading behavior

## Solution: Two Strategies

### 1. `wait_for_buy` (Conservative - Default)

**Behavior:**
- Only places buy orders initially
- Sell orders are placed only after corresponding buy orders are filled
- Ensures you never try to sell shares you don't own

**Advantages:**
- Safe and conservative approach
- No risk of short positions
- Gradually builds position as market moves

**Best for:**
- Risk-averse traders
- Accounts that don't allow short selling
- Building positions from zero

### 2. `buy_at_market` (Aggressive)

**Behavior:**
- Calculates total shares needed for all sell orders
- Buys shares at current market price immediately
- Places all sell orders once shares are acquired

**Advantages:**
- Full grid active immediately
- Maximum profit potential from day one
- Symmetric buy/sell grid operation

**Best for:**
- Experienced traders
- When you want maximum grid coverage
- Bull market conditions

## Configuration

Add this setting to your `grid_config.json` file:

```json
{
  "execution_settings": {
    "initial_position_strategy": "wait_for_buy",
    "comment": "Options: 'wait_for_buy' or 'buy_at_market'"
  }
}
```

## Example Scenarios

### Scenario 1: wait_for_buy Strategy

```
Initial State: 0 shares
Grid Setup:
- Buy orders: 7 orders placed ✅
- Sell orders: 0 orders placed (waiting)

After first buy order fills (+10 shares):
- New sell order placed for those 10 shares ✅
- Remaining sell orders still waiting

Result: Conservative, gradual position building
```

### Scenario 2: buy_at_market Strategy

```
Initial State: 0 shares
Step 1: Calculate total shares needed = 43 shares
Step 2: Buy 43 shares at market price ✅
Step 3: Place all grid orders:
- Buy orders: 7 orders placed ✅
- Sell orders: 7 orders placed ✅

Result: Full grid active immediately
```

## Risk Considerations

### wait_for_buy Risks:
- Slower to capture upward price movements
- May miss profit opportunities if price rises quickly
- Grid may be unbalanced initially

### buy_at_market Risks:
- Higher initial capital requirement
- Market order may have unfavorable fill price
- Full position exposure from start
- May buy at local high

## Implementation Details

The bot automatically:
1. Tracks current position (`current_position`)
2. Calculates available shares for sell orders
3. Places pending sell orders when shares become available
4. Updates grid dynamically as orders fill

## Monitoring

The bot logs will show:
- Current position status
- Strategy being used
- Order placement decisions
- Share availability calculations

Example log messages:
```
INFO - Initial Position Strategy: wait_for_buy
INFO - Current position: 0 shares
INFO - No shares in position - no sell orders placed
INFO - Placed pending sell order: 10 @ 71.05
```

## Backward Compatibility

- Default strategy is `wait_for_buy` (safe option)
- Existing configurations without this setting will use `wait_for_buy`
- No changes needed to existing bot installations

## Testing

Use the included `test_strategy.py` script to test both strategies without placing real orders:

```bash
python test_strategy.py
```

This will show you what the bot would do with each strategy given current market conditions.
