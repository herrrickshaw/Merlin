#!/usr/bin/env python3
"""
Chaikin Money Flow (CMF) Accumulation Analysis
Demonstrates how CMF identifies stocks in accumulation phase
"""

import random
import statistics
from datetime import datetime, timedelta

# Chaikin Money Flow calculation
def chaikin_money_flow(candles, period=20):
    """Calculate CMF over specified period"""
    if len(candles) < period:
        return None

    recent = candles[-period:]
    money_flow = []
    volumes = []

    for candle in recent:
        high, low, close, volume = candle['high'], candle['low'], candle['close'], candle['volume']

        hl_diff = high - low
        if hl_diff == 0:
            mf_multiplier = 0
        else:
            mf_multiplier = ((close - low) - (high - close)) / hl_diff

        money_flow.append(mf_multiplier * volume)
        volumes.append(volume)

    total_mf = sum(money_flow)
    total_volume = sum(volumes)

    if total_volume == 0:
        return None

    return total_mf / total_volume

def cmf_signal(cmf_value):
    """Classify CMF value into accumulation/distribution status"""
    if cmf_value is None:
        return "INSUFFICIENT_DATA"
    elif cmf_value > 0.25:
        return "STRONG_ACCUMULATION"
    elif cmf_value > 0.05:
        return "ACCUMULATION"
    elif cmf_value > -0.05:
        return "NEUTRAL"
    elif cmf_value > -0.25:
        return "DISTRIBUTION"
    else:
        return "STRONG_DISTRIBUTION"

def is_accumulation_phase(cmf_value):
    """Check if stock is in accumulation phase"""
    if cmf_value is None:
        return False
    return cmf_value > 0.05

def generate_candles(symbol, num_candles=252, base_price=100, trend='accumulation'):
    """Generate synthetic OHLCV candles"""
    candles = []
    price = base_price
    date = datetime.now() - timedelta(days=num_candles)

    for i in range(num_candles):
        # Trend-based price movement
        if trend == 'accumulation':
            # Accumulation: small upward trend with heavy volume on up days
            trend_factor = random.uniform(0.98, 1.02)
            if random.random() > 0.4:  # 60% chance of up day
                trend_factor = random.uniform(1.00, 1.03)
        elif trend == 'distribution':
            # Distribution: small downward trend with heavy volume on down days
            trend_factor = random.uniform(0.98, 1.02)
            if random.random() > 0.6:  # 40% chance of up day
                trend_factor = random.uniform(0.98, 1.00)
        else:  # neutral
            trend_factor = random.uniform(0.99, 1.01)

        price = price * trend_factor

        # Generate OHLCV
        open_price = price * random.uniform(0.99, 1.00)
        close_price = price * random.uniform(0.99, 1.01)
        high_price = max(open_price, close_price) * random.uniform(1.00, 1.02)
        low_price = min(open_price, close_price) * random.uniform(0.98, 1.00)

        # Volume: higher on accumulation, normal on distribution
        base_volume = 1_000_000
        if trend == 'accumulation' and close_price > open_price:
            volume = base_volume * random.uniform(1.5, 2.5)
        elif trend == 'distribution' and close_price < open_price:
            volume = base_volume * random.uniform(1.5, 2.5)
        else:
            volume = base_volume * random.uniform(0.8, 1.2)

        candles.append({
            'date': date.strftime('%Y-%m-%d'),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': int(volume),
        })

        date += timedelta(days=1)

    return candles

def analyze_accumulation(symbol, candles):
    """Analyze accumulation phase for a stock"""
    cmf_20 = chaikin_money_flow(candles, 20)
    cmf_50 = chaikin_money_flow(candles, 50)

    status = cmf_signal(cmf_20)
    in_accumulation = is_accumulation_phase(cmf_20)

    # Confidence scoring
    if cmf_20 is None:
        confidence = 0.0
    elif cmf_20 > 0.25:
        confidence = 0.95
    elif cmf_20 > 0.05:
        confidence = 0.75
    elif cmf_20 > -0.05:
        confidence = 0.50
    else:
        confidence = 0.25

    return {
        'symbol': symbol,
        'cmf_20': cmf_20,
        'cmf_50': cmf_50,
        'status': status,
        'in_accumulation': in_accumulation,
        'confidence': confidence,
    }

# Test three market phases
def main():
    print("\n" + "="*90)
    print("CHAIKIN MONEY FLOW - ACCUMULATION PHASE ANALYSIS")
    print("="*90)

    # Scenario 1: Accumulation Phase
    print("\n" + "─"*90)
    print("📈 SCENARIO 1: ACCUMULATION PHASE")
    print("─"*90)
    print("Market condition: Institutional buyers accumulating, price slowly rising")
    print("CMF Signal: Positive (>0.05) with increasing volume on up days\n")

    results_accum = []
    for i in range(5):
        symbol = f"ACCUM_{i+1:02d}"
        candles = generate_candles(symbol, trend='accumulation')
        analysis = analyze_accumulation(symbol, candles)
        results_accum.append(analysis)

        print(f"  {symbol:<12} | CMF(20): {analysis['cmf_20']:>7.4f} | CMF(50): {analysis['cmf_50']:>7.4f} | "
              f"Status: {analysis['status']:<20} | Confidence: {analysis['confidence']:.0%}")

    # Scenario 2: Neutral Phase
    print("\n" + "─"*90)
    print("➡️  SCENARIO 2: NEUTRAL PHASE")
    print("─"*90)
    print("Market condition: Balanced buy/sell pressure, random price movement")
    print("CMF Signal: Near zero (-0.05 to 0.05)\n")

    results_neutral = []
    for i in range(5):
        symbol = f"NEUTRAL_{i+1:02d}"
        candles = generate_candles(symbol, trend='neutral')
        analysis = analyze_accumulation(symbol, candles)
        results_neutral.append(analysis)

        print(f"  {symbol:<12} | CMF(20): {analysis['cmf_20']:>7.4f} | CMF(50): {analysis['cmf_50']:>7.4f} | "
              f"Status: {analysis['status']:<20} | Confidence: {analysis['confidence']:.0%}")

    # Scenario 3: Distribution Phase
    print("\n" + "─"*90)
    print("📉 SCENARIO 3: DISTRIBUTION PHASE")
    print("─"*90)
    print("Market condition: Institutional sellers distributing, price slowly falling")
    print("CMF Signal: Negative (<-0.05) with increasing volume on down days\n")

    results_dist = []
    for i in range(5):
        symbol = f"DISTRIB_{i+1:02d}"
        candles = generate_candles(symbol, trend='distribution')
        analysis = analyze_accumulation(symbol, candles)
        results_dist.append(analysis)

        print(f"  {symbol:<12} | CMF(20): {analysis['cmf_20']:>7.4f} | CMF(50): {analysis['cmf_50']:>7.4f} | "
              f"Status: {analysis['status']:<20} | Confidence: {analysis['confidence']:.0%}")

    # Summary statistics
    print("\n" + "="*90)
    print("📊 STATISTICAL SUMMARY")
    print("="*90)

    accum_cmf = [a['cmf_20'] for a in results_accum if a['cmf_20'] is not None]
    neutral_cmf = [n['cmf_20'] for n in results_neutral if n['cmf_20'] is not None]
    dist_cmf = [d['cmf_20'] for d in results_dist if d['cmf_20'] is not None]

    print(f"\nAccumulation Phase:")
    print(f"  Average CMF(20): {statistics.mean(accum_cmf):.4f}")
    print(f"  StdDev:          {statistics.stdev(accum_cmf):.4f}")
    print(f"  Range:           [{min(accum_cmf):.4f}, {max(accum_cmf):.4f}]")
    print(f"  Stocks in accum: {sum(1 for a in results_accum if a['in_accumulation'])}/{len(results_accum)}")

    print(f"\nNeutral Phase:")
    print(f"  Average CMF(20): {statistics.mean(neutral_cmf):.4f}")
    print(f"  StdDev:          {statistics.stdev(neutral_cmf):.4f}")
    print(f"  Range:           [{min(neutral_cmf):.4f}, {max(neutral_cmf):.4f}]")
    print(f"  Stocks in accum: {sum(1 for n in results_neutral if n['in_accumulation'])}/{len(results_neutral)}")

    print(f"\nDistribution Phase:")
    print(f"  Average CMF(20): {statistics.mean(dist_cmf):.4f}")
    print(f"  StdDev:          {statistics.stdev(dist_cmf):.4f}")
    print(f"  Range:           [{min(dist_cmf):.4f}, {max(dist_cmf):.4f}]")
    print(f"  Stocks in accum: {sum(1 for d in results_dist if d['in_accumulation'])}/{len(results_dist)}")

    # Integration with pipeline
    print("\n" + "="*90)
    print("🔄 PIPELINE INTEGRATION")
    print("="*90)
    print("""
Stage 1 (Darvas Box):     Detects price breakouts (momentum)
Stage 2 (Piotroski F-Score): Validates financial strength
Stage 3 (Coffee Can):      Confirms quality compounder characteristics
→ Stage 4 (CMF):          Verifies accumulation phase (smart money buying)
     └─ Output: Only triple hits with accumulation confirmation

CMF Advantages:
  ✓ Volume confirmation that breakouts are legitimate
  ✓ Detects institutional accumulation before price spike
  ✓ Identifies low-volume breakouts (false signals)
  ✓ Reduces false positives in pipeline
  ✓ Independent of price action - validates money flow
""")

    # Practical signals
    print("\n" + "="*90)
    print("🎯 PRACTICAL ACCUMULATION SIGNALS")
    print("="*90)

    strong_accum = [a for a in results_accum if a['cmf_20'] is not None and a['cmf_20'] > 0.25]
    regular_accum = [a for a in results_accum if a['cmf_20'] is not None and 0.05 < a['cmf_20'] <= 0.25]

    print(f"\n✅ STRONG ACCUMULATION (CMF > 0.25):")
    for stock in strong_accum[:3]:
        print(f"   {stock['symbol']}: CMF = {stock['cmf_20']:.4f}")
        print(f"   → Signal: Institutions heavily buying, high conviction")

    print(f"\n⚠️  REGULAR ACCUMULATION (CMF 0.05-0.25):")
    for stock in regular_accum[:3]:
        print(f"   {stock['symbol']}: CMF = {stock['cmf_20']:.4f}")
        print(f"   → Signal: Moderate institutional buying, watch for breakout")

    print("\n" + "="*90)
    print("✅ CMF ACCUMULATION FILTER READY")
    print("="*90 + "\n")

if __name__ == "__main__":
    random.seed(42)  # For reproducibility
    main()
