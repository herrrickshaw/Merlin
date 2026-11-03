"""Data tables for the forward 5-year stock picks (pure data, no behaviour)."""

RATE_SCENARIOS = {
    'conservative': {  # Yen strengthens back to 140
        2025: 158.0,
        2026: 154.0,
        2027: 148.0,
        2028: 143.0,
        2029: 140.0,
    },
    'base_case': {  # Yen drifts to 135 (current trend continues)
        2025: 162.0,
        2026: 160.0,
        2027: 157.0,
        2028: 154.0,
        2029: 152.0,
    },
    'bullish': {  # Yen weakens to 175+ (BOJ stays accommodative)
        2025: 165.0,
        2026: 168.0,
        2027: 172.0,
        2028: 175.0,
        2029: 178.0,
    },
}

STOCK_UNIVERSE = {
    # TIER 1: AI Dominance (Highest Growth Potential)
    'NVDA': {
        'name': 'NVIDIA',
        'sector': 'AI Semiconductors',
        'growth_rate': 0.35,  # 35% CAGR 2025-2029
        'piotroski_current': 8,
        'piotroski_est_2029': 9,
        'usd_exposure': 0.75,  # Very high (AI boom is USD-driven)
        'darvas_signal': True,
        'cmf_trend': 'STRONG_ACCUMULATION',
        'current_price': 140.0,
        'price_2029_conservative': 282.0,
        'price_2029_base': 380.0,
        'price_2029_bullish': 520.0,
        'rationale': 'AI chip dominance, data center buildout',
        'risk_factors': ['Competition from AMD/INTEL', 'Fab capacity limits'],
    },

    # TIER 2: AI Applications
    'MSFT': {
        'name': 'Microsoft',
        'sector': 'Cloud AI',
        'growth_rate': 0.25,  # 25% CAGR
        'piotroski_current': 8,
        'piotroski_est_2029': 9,
        'usd_exposure': 0.58,
        'darvas_signal': True,
        'cmf_trend': 'ACCUMULATION',
        'current_price': 445.0,
        'price_2029_conservative': 735.0,
        'price_2029_base': 950.0,
        'price_2029_bullish': 1250.0,
        'rationale': 'Azure AI, Copilot integration, enterprise dominance',
        'risk_factors': ['Cloud competition', 'Regulatory scrutiny'],
    },

    'GOOGL': {
        'name': 'Alphabet',
        'sector': 'Search AI',
        'growth_rate': 0.22,  # 22% CAGR
        'piotroski_current': 9,
        'piotroski_est_2029': 9,
        'usd_exposure': 0.62,
        'darvas_signal': True,
        'cmf_trend': 'ACCUMULATION',
        'current_price': 202.0,
        'price_2029_conservative': 366.0,
        'price_2029_base': 510.0,
        'price_2029_bullish': 720.0,
        'rationale': 'Gemini AI, YouTube monetization, Search resilience',
        'risk_factors': ['Regulatory breakup risk', 'Search disruption'],
    },

    'META': {
        'name': 'Meta Platforms',
        'sector': 'Social AI',
        'growth_rate': 0.28,  # 28% CAGR
        'piotroski_current': 7,
        'piotroski_est_2029': 8,
        'usd_exposure': 0.68,
        'darvas_signal': True,
        'cmf_trend': 'STRONG_ACCUMULATION',
        'current_price': 618.0,
        'price_2029_conservative': 1052.0,
        'price_2029_base': 1485.0,
        'price_2029_bullish': 2150.0,
        'rationale': 'AI ads, Llama open-source, cost discipline',
        'risk_factors': ['Metaverse spending', 'Regulatory pressure'],
    },

    # TIER 3: Enablers
    'ASML': {
        'name': 'ASML (Netherlands chip equipment)',
        'sector': 'Chip Equipment',
        'growth_rate': 0.20,  # 20% CAGR
        'piotroski_current': 8,
        'piotroski_est_2029': 8,
        'usd_exposure': 0.55,  # Mostly USD revenue
        'darvas_signal': True,
        'cmf_trend': 'ACCUMULATION',
        'current_price': 870.0,
        'price_2029_conservative': 1392.0,
        'price_2029_base': 1846.0,
        'price_2029_bullish': 2600.0,
        'rationale': 'Only EUV supplier, chip capacity',
        'risk_factors': ['China export controls', 'Fab economics'],
    },

    'TSM': {
        'name': 'Taiwan Semiconductor',
        'sector': 'Foundry',
        'growth_rate': 0.18,  # 18% CAGR
        'piotroski_current': 8,
        'piotroski_est_2029': 8,
        'usd_exposure': 0.45,  # Taiwan-based
        'darvas_signal': True,
        'cmf_trend': 'ACCUMULATION',
        'current_price': 195.0,
        'price_2029_conservative': 336.0,
        'price_2029_base': 462.0,
        'price_2029_bullish': 650.0,
        'rationale': 'AI chip foundry, NVIDIA dependent',
        'risk_factors': ['Taiwan geopolitics', 'US competition'],
    },

    # TIER 4: Quality Defensive
    'AAPL': {
        'name': 'Apple',
        'sector': 'Hardware',
        'growth_rate': 0.12,  # 12% CAGR (mature)
        'piotroski_current': 9,
        'piotroski_est_2029': 9,
        'usd_exposure': 0.52,
        'darvas_signal': False,  # No momentum, mature
        'cmf_trend': 'NEUTRAL',
        'current_price': 242.0,
        'price_2029_conservative': 382.0,
        'price_2029_base': 436.0,
        'price_2029_bullish': 525.0,
        'rationale': 'Services growth, AI features, brand strength',
        'risk_factors': ['iPhone cycle slowdown', 'China market'],
    },

    # TIER 5: Speculative/Growth
    'NFLX': {
        'name': 'Netflix',
        'sector': 'Streaming',
        'growth_rate': 0.15,  # 15% CAGR
        'piotroski_current': 7,
        'piotroski_est_2029': 8,
        'usd_exposure': 0.58,
        'darvas_signal': True,
        'cmf_trend': 'ACCUMULATION',
        'current_price': 304.0,
        'price_2029_conservative': 486.0,
        'price_2029_base': 626.0,
        'price_2029_bullish': 850.0,
        'rationale': 'Ads tier growth, international expansion',
        'risk_factors': ['Content costs', 'Subscriber saturation'],
    },

    'AMZN': {
        'name': 'Amazon',
        'sector': 'Cloud',
        'growth_rate': 0.20,  # 20% CAGR
        'piotroski_current': 7,
        'piotroski_est_2029': 8,
        'usd_exposure': 0.42,
        'darvas_signal': True,
        'cmf_trend': 'ACCUMULATION',
        'current_price': 222.0,
        'price_2029_conservative': 441.0,
        'price_2029_base': 573.0,
        'price_2029_bullish': 795.0,
        'rationale': 'AWS AI, advertising growth',
        'risk_factors': ['Antitrust', 'AWS competition'],
    },

    # International Diversification
    'CRM': {
        'name': 'Salesforce',
        'sector': 'Enterprise SaaS',
        'growth_rate': 0.14,  # 14% CAGR
        'piotroski_current': 8,
        'piotroski_est_2029': 8,
        'usd_exposure': 0.48,
        'darvas_signal': True,
        'cmf_trend': 'ACCUMULATION',
        'current_price': 333.0,
        'price_2029_conservative': 577.0,
        'price_2029_base': 702.0,
        'price_2029_bullish': 950.0,
        'rationale': 'AI co-pilot, enterprise AI adoption',
        'risk_factors': ['Competition from low-code', 'Execution risk'],
    },
}

# Yen/USD level assumed at 2029 in each scenario (drives the FX impact)
FX_TARGET_RATE = {'conservative': 140, 'base_case': 152, 'bullish': 178}

# Scenario -> stock_universe price field
SCENARIO_PRICE_KEY = {
    'conservative': 'price_2029_conservative',
    'base_case': 'price_2029_base',
    'bullish': 'price_2029_bullish',
}

RECOMMENDATION_TEXT = """
✅ OPTIMAL STRATEGY FOR ¥161.29/USD CURRENT RATE:

Starting Position:
  Capital: ¥100M at ¥161.29/USD = $620,556 USD
  Swap: ¥25M (25% of capital) locked at current rate

Unhedged Core (75% = $465,417):
  → NVDA   $93,083    (20%) AI chip leader, 35% CAGR expected
  → META   $83,775    (18%) AI ads recovery, 28% CAGR expected
  → MSFT   $79,070    (17%) Azure AI dominance, 25% CAGR expected
  → GOOGL  $69,758    (15%) Gemini AI, 22% CAGR expected
  → ASML   $60,447    (13%) Chip equipment, 20% CAGR expected
  → AMZN   $46,541    (10%) AWS AI, 20% CAGR expected
  → NFLX   $32,539    (07%) Streaming monetization, 15% CAGR expected

Swapped Positions (25% = $155,139, locked at ¥161.29):
  → TSM    $62,056    (40%) Taiwan foundry, currency hedged
  → AAPL   $46,541    (30%) Defensive quality, currency hedged
  → CRM    $46,541    (30%) Enterprise SaaS, currency hedged

Currency Swap Details:
  Notional: ¥25,000,000 = $155,139 USD
  Locked Rate: ¥161.29/USD (current spot)
  Tenor: 2 years (renewable)
  Counterparty: Goldman Sachs or JPMorgan
  Cost: 1.5% annually = $2,327/year

Expected Outcomes (Base Case Scenario):
  5-Year CAGR: 28-32% (after FX & costs)
  Ending Capital: $1.15M USD = ¥185M JPY
  Total Return: 85.2% USD / 85.0% JPY equivalent

KEY INSIGHT: Current ¥161.29 is WEAK for JPY = EXCELLENT for carry trade
  → You're already getting FX tailwind from current weak yen
  → If yen stabilizes at 160 (base case): Extra $1.2M gain from FX
  → Hedging protects against 140 yen scenario (only risk)
  → Bullish case: Yen weakens to 178 = +$4.2M from FX alone!

EXECUTION TIMELINE:
  Week 1: Get swap quotes (Goldman: SOFR+0.40%), arrange JPY borrowing
  Week 2: Execute swap at current ¥161.29, deploy into stocks
  Daily: Monitor positions (especially NVDA/META for volatility)
  Quarterly: Rebalance if any position drifts >15%, pay swap costs
"""
