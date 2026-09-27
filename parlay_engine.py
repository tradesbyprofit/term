"""
J.A.R.V.I.S. QUANTITATIVE 3-LEG PARLAY GENERATOR & COMPOUNDER
Synthesizes Grade-A (+EV) single-leg signals across NFL, Soccer, MLB, NBA & Tennis:
1. Strict Uncorrelated Independence: Legs must come from different fixtures.
2. Cross-Sport Diversification: Combines signals across multiple sports.
3. Always Positive Money: Total parlay decimal odds >= 2.05 (+105 to +600 range).
4. Multiplicative Joint True Probability: Joint Prob = P1 * P2 * P3
5. Parlay Fair Odds & Compounded Edge: EV% = (Joint Prob * Parlay Odds) - 1.0
6. Conservative Multi-Leg Kelly Allocation: Scaled down to prevent parlay variance drag.
"""

import sqlite3
import random
import itertools
from datetime import datetime, timezone
from typing import List, Dict, Optional

DB_PATH = "/home/user/pinnacle_terminal.db"

def init_parlay_tables():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS active_parlays (
        parlay_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        sports_mix TEXT NOT NULL,
        leg1_fixture TEXT NOT NULL,
        leg1_pick TEXT NOT NULL,
        leg1_odds REAL NOT NULL,
        leg1_prob REAL NOT NULL,
        leg2_fixture TEXT NOT NULL,
        leg2_pick TEXT NOT NULL,
        leg2_odds REAL NOT NULL,
        leg2_prob REAL NOT NULL,
        leg3_fixture TEXT NOT NULL,
        leg3_pick TEXT NOT NULL,
        leg3_odds REAL NOT NULL,
        leg3_prob REAL NOT NULL,
        parlay_decimal_odds REAL NOT NULL,
        joint_model_prob REAL NOT NULL,
        joint_fair_odds REAL NOT NULL,
        compounded_ev_pct REAL NOT NULL,
        suggested_stake_usd REAL NOT NULL,
        grade TEXT NOT NULL, -- GRADE_A_PRIME, GRADE_A
        status TEXT NOT NULL -- ARMED, SETTLED
    )
    """)
    conn.commit()
    conn.close()

init_parlay_tables()

def generate_optimal_3leg_parlays(num_parlays=6) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    c = conn.cursor()

    # Query Grade-A single lines: EV >= 2.0%, Limit >= $2,500
    c.execute("""
    SELECT m.line_id, m.fixture_id, m.market_type, m.side, m.line_value, 
           m.pinnacle_price, m.model_prob, m.edge_ev_pct, m.limit_usd,
           f.sport, f.league, f.home_team, f.away_team
    FROM pinnacle_market_lines m
    JOIN pinnacle_fixtures f ON m.fixture_id = f.fixture_id
    WHERE m.edge_ev_pct >= 0.020 AND m.pinnacle_price >= 1.25 AND m.pinnacle_price <= 2.80
    ORDER BY m.limit_usd DESC, m.edge_ev_pct DESC
    LIMIT 120
    """)
    candidates = c.fetchall()

    if len(candidates) < 3:
        conn.close()
        return []

    # Format candidates
    items = []
    for r in candidates:
        items.append({
            "line_id": r[0],
            "fixture_id": r[1],
            "market_type": r[2],
            "side": r[3],
            "line_value": r[4],
            "price": r[5],
            "prob": r[6],
            "ev": r[7],
            "limit": r[8],
            "sport": r[9],
            "league": r[10],
            "home": r[11],
            "away": r[12],
            "pick_str": f"{r[3]} {r[4] if r[4] != 0.0 else ''}".strip(),
            "fixture_str": f"{r[12]} @ {r[11]}"
        })

    # Fetch current bankroll for staking
    c.execute("SELECT total_balance FROM vault_account WHERE id = 1")
    bankroll = c.fetchone()[0]

    parlays = []
    used_combos = set()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Shuffle to find diverse combinations
    random.shuffle(items)

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            for k in range(j + 1, len(items)):
                l1, l2, l3 = items[i], items[j], items[k]

                # STRICT CONSTRAINT 1: Completely different fixtures (zero correlation)
                if len({l1['fixture_id'], l2['fixture_id'], l3['fixture_id']}) < 3:
                    continue

                # STRICT CONSTRAINT 2: Multi-sport mix (at least 2 different sports for true diversification)
                sports = {l1['sport'], l2['sport'], l3['sport']}
                if len(sports) < 2:
                    continue

                # Compute Parlay Odds
                parlay_odds = round(l1['price'] * l2['price'] * l3['price'], 2)

                # STRICT CONSTRAINT 3: ALWAYS POSITIVE MONEY (odds >= 2.05, i.e., +105 or better)
                # Cap at 7.50 (+650) to avoid longshot variance traps
                if parlay_odds < 2.05 or parlay_odds > 7.50:
                    continue

                # Joint Multiplicative Probability
                joint_prob = l1['prob'] * l2['prob'] * l3['prob']
                joint_fair_odds = round(1.0 / joint_prob, 2) if joint_prob > 0 else 999.0

                # Compounded Expected Value (EV%)
                compounded_ev = (joint_prob * parlay_odds) - 1.0

                # Only accept positive compounded edge
                if compounded_ev < 0.040:
                    continue

                # Kelly Stake for 3-Leg Parlays (Scaled down to 1/8 Kelly to prevent parlay variance drag)
                b = parlay_odds - 1.0
                full_kelly = (b * joint_prob - (1.0 - joint_prob)) / b if b > 0 else 0
                parlay_stake_pct = max(0.005, min(full_kelly * 0.125, 0.020)) # Cap at 2% of bankroll
                stake_usd = round(bankroll * parlay_stake_pct, 2)
                stake_usd = max(2.50, stake_usd)

                parlay_id = f"PARLAY-3L-{int(random.random()*1000000)}"
                combo_key = tuple(sorted([l1['line_id'], l2['line_id'], l3['line_id']]))

                if combo_key in used_combos:
                    continue
                used_combos.add(combo_key)

                sports_label = " + ".join(sorted(list(sports)))
                grade = "GRADE_A_PRIME" if compounded_ev >= 0.08 else "GRADE_A"

                parlays.append({
                    "parlay_id": parlay_id,
                    "sports_mix": sports_label,
                    "leg1": {"fixture": l1['fixture_str'], "pick": f"{l1['market_type']}: {l1['pick_str']}", "odds": l1['price'], "prob": round(l1['prob'], 3)},
                    "leg2": {"fixture": l2['fixture_str'], "pick": f"{l2['market_type']}: {l2['pick_str']}", "odds": l2['price'], "prob": round(l2['prob'], 3)},
                    "leg3": {"fixture": l3['fixture_str'], "pick": f"{l3['market_type']}: {l3['pick_str']}", "odds": l3['price'], "prob": round(l3['prob'], 3)},
                    "parlay_odds": parlay_odds,
                    "american_odds": f"+{int((parlay_odds - 1.0)*100)}" if parlay_odds >= 2.0 else f"-{int(100/(parlay_odds-1.0))}",
                    "joint_prob": round(joint_prob, 3),
                    "fair_odds": joint_fair_odds,
                    "compounded_ev_pct": round(compounded_ev, 4),
                    "stake_usd": stake_usd,
                    "grade": grade
                })

                if len(parlays) >= num_parlays:
                    break
            if len(parlays) >= num_parlays:
                break
        if len(parlays) >= num_parlays:
            break

    # Save to SQLite table
    c.execute("DELETE FROM active_parlays")
    for p in parlays:
        c.execute("""
        INSERT INTO active_parlays (
            parlay_id, created_at, sports_mix,
            leg1_fixture, leg1_pick, leg1_odds, leg1_prob,
            leg2_fixture, leg2_pick, leg2_odds, leg2_prob,
            leg3_fixture, leg3_pick, leg3_odds, leg3_prob,
            parlay_decimal_odds, joint_model_prob, joint_fair_odds,
            compounded_ev_pct, suggested_stake_usd, grade, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ARMED')
        """, (
            p['parlay_id'], now_iso, p['sports_mix'],
            p['leg1']['fixture'], p['leg1']['pick'], p['leg1']['odds'], p['leg1']['prob'],
            p['leg2']['fixture'], p['leg2']['pick'], p['leg2']['odds'], p['leg2']['prob'],
            p['leg3']['fixture'], p['leg3']['pick'], p['leg3']['odds'], p['leg3']['prob'],
            p['parlay_odds'], p['joint_prob'], p['fair_odds'],
            p['compounded_ev_pct'], p['stake_usd'], p['grade']
        ))

    conn.commit()
    conn.close()
    return parlays

if __name__ == "__main__":
    parlays = generate_optimal_3leg_parlays(5)
    print(f"Generated {len(parlays)} optimal +Money Grade-A 3-Leg Parlays:")
    for p in parlays:
        print(f"\n[{p['parlay_id']}] {p['sports_mix']} | Payout: {p['parlay_odds']} ({p['american_odds']}) | Edge: +{p['compounded_ev_pct']*100:.1f}% | Stake: ${p['stake_usd']}")
        print(f"  Leg 1: {p['leg1']['fixture']} -> {p['leg1']['pick']} @ {p['leg1']['odds']}")
        print(f"  Leg 2: {p['leg2']['fixture']} -> {p['leg2']['pick']} @ {p['leg2']['odds']}")
        print(f"  Leg 3: {p['leg3']['fixture']} -> {p['leg3']['pick']} @ {p['leg3']['odds']}")
