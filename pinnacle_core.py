"""
PINNACLE HIGH-FREQUENCY QUANTITATIVE TRADING ENGINE
Reverse-engineered to Pinnacle API Architecture (Fixtures, Lines, Limits & Dropping Odds)
Integrated with:
1. Logarithmic Multiplicative Power De-vigging (Pinnacle Todd Fair Odds)
2. Live Market Limit Usd Tracking (Limit as Confidence Metric)
3. Line Shift Velocity (Steam Chaser & Dropping Odds Detection)
4. Andrew Mack Latent Process Strikeout & Derivative Prop Pricing
5. Quarter-Kelly Risk Sizing & Dynamic Liquidity Capping
6. SQLite High-Speed Persistent WAL Database
"""

import math
import random
import time
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Tuple
import numpy as np
from scipy.stats import poisson

DB_PATH = "/home/user/pinnacle_terminal.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    # Pinnacle Live Matchups & Fixtures
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pinnacle_fixtures (
        fixture_id INTEGER PRIMARY KEY,
        sport TEXT NOT NULL,
        league TEXT NOT NULL,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        event_time TEXT NOT NULL,
        status TEXT NOT NULL,
        pitcher_home TEXT,
        pitcher_away TEXT,
        updated_at TEXT NOT NULL
    )
    """)

    # Pinnacle Lines, Limits & Vig Telemetry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pinnacle_market_lines (
        line_id TEXT PRIMARY KEY,
        fixture_id INTEGER NOT NULL,
        market_type TEXT NOT NULL, -- Strikeouts, Moneyline, Spread, Total
        period INTEGER NOT NULL, -- 0=Full Game, 1=1st 5 Innings
        line_value REAL,
        side TEXT NOT NULL, -- Over, Under, Home, Away
        pinnacle_price REAL NOT NULL, -- Decimal Odds
        prev_price REAL,
        price_delta_pct REAL DEFAULT 0.0,
        limit_usd REAL NOT NULL, -- Live Max Accepted Stake
        limit_tier TEXT NOT NULL, -- Overnight ($500), Midday ($5k), Game-Time Max ($20k+)
        overround REAL NOT NULL, -- Book Margin % (e.g. 0.024)
        true_fair_odds REAL NOT NULL, -- Margin-removed fair odds (Pinnacle Todd)
        true_fair_prob REAL NOT NULL,
        model_prob REAL NOT NULL,
        edge_ev_pct REAL NOT NULL,
        signal TEXT NOT NULL, -- STEAM_BUY, +EV_LIMIT_SNIPE, PASS
        updated_at TEXT NOT NULL,
        FOREIGN KEY(fixture_id) REFERENCES pinnacle_fixtures(fixture_id)
    )
    """)

    # Line Movement History (Time-series for Steam & Sharp Money Flow)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS line_movement_ticks (
        tick_id INTEGER PRIMARY KEY AUTOINCREMENT,
        line_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        price REAL NOT NULL,
        limit_usd REAL NOT NULL,
        event_type TEXT NOT NULL -- STEAM_DROP, LIMIT_INCREASE, NORMAL_DRIFT
    )
    """)

    # Algorithmic Trading Orders & Execution Ledger
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS execution_orders (
        order_id TEXT PRIMARY KEY,
        line_id TEXT NOT NULL,
        placed_at TEXT NOT NULL,
        fixture_name TEXT NOT NULL,
        selection TEXT NOT NULL,
        market_type TEXT NOT NULL,
        entry_price REAL NOT NULL,
        closing_price REAL,
        clv_pct REAL,
        limit_usd REAL NOT NULL,
        order_size_usd REAL NOT NULL,
        bankroll_pct REAL NOT NULL,
        status TEXT NOT NULL, -- EXECUTED, SETTLED
        outcome INTEGER, -- 1=Win, 0=Loss
        actual_count REAL,
        pnl_usd REAL
    )
    """)

    # Vault & Bankroll State
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vault_account (
        id INTEGER PRIMARY KEY,
        total_balance REAL NOT NULL,
        available_cash REAL NOT NULL,
        allocated_in_flight REAL NOT NULL,
        high_water_mark REAL NOT NULL,
        max_drawdown_pct REAL NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # System Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS terminal_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        severity TEXT NOT NULL,
        module TEXT NOT NULL,
        message TEXT NOT NULL
    )
    """)

    cursor.execute("SELECT COUNT(*) FROM vault_account")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO vault_account (id, total_balance, available_cash, allocated_in_flight, high_water_mark, max_drawdown_pct, updated_at)
        VALUES (1, 25000.00, 25000.00, 0.00, 25000.00, 0.0, ?)
        """, (datetime.now(timezone.utc).isoformat(),))

    conn.commit()
    conn.close()

init_db()

class PinnacleQuantitativeEngine:
    """
    Implements true sharp line mechanics:
    1. Shin / Logarithmic Margin Removal (De-vigging)
    2. Mack's Latent Process Whiff Decomposition
    3. Poisson Cumulative Tail Modeling
    4. Limit-Weighted Kelly Execution (Stark Syndicate Algorithm)
    """
    @staticmethod
    def devig_two_way_power(price_1: float, price_2: float) -> Tuple[float, float, float]:
        """
        Calculates exact fair odds removing Pinnacle's overround.
        Uses power method: (1/O1)^k + (1/O2)^k = 1.0
        Returns (fair_prob1, fair_prob2, overround)
        """
        imp1 = 1.0 / price_1
        imp2 = 1.0 / price_2
        overround = (imp1 + imp2) - 1.0

        # Iterative search for power k
        k = 1.0
        for _ in range(12):
            val = (imp1 ** k) + (imp2 ** k)
            if abs(val - 1.0) < 1e-6:
                break
            deriv = (imp1 ** k) * math.log(imp1) + (imp2 ** k) * math.log(imp2)
            if deriv != 0:
                k -= (val - 1.0) / deriv

        fair_p1 = imp1 ** k
        fair_p2 = imp2 ** k
        norm_sum = fair_p1 + fair_p2
        return fair_p1 / norm_sum, fair_p2 / norm_sum, overround

    @staticmethod
    def calculate_mack_lambda(sw_str: float, look_str: float, foul_str: float,
                              opp_k_pct: float, exp_ip: float, bf_inn: float) -> float:
        """Decomposes pitch mechanics into Poisson expected strikeout count."""
        beta_0 = -0.152
        beta_sw = 1.845
        beta_look = 0.620
        beta_foul = 0.310
        base_k_rate = beta_0 + (beta_sw * sw_str) + (beta_look * look_str) + (beta_foul * foul_str)
        opp_factor = opp_k_pct / 0.225 # MLB Avg
        return max(base_k_rate * opp_factor * (exp_ip * bf_inn), 0.5)

    @staticmethod
    def price_poisson_tail(lam: float, line: float, side: str) -> float:
        floor_k = int(math.floor(line))
        if side.upper() == "OVER":
            return 1.0 - float(poisson.cdf(floor_k, lam))
        else:
            return float(poisson.cdf(floor_k, lam))

    @staticmethod
    def limit_weighted_kelly(bankroll: float, model_prob: float, price: float, limit_usd: float) -> Tuple[float, float]:
        """
        Kelly sizing with liquidity-limit weighting and maximum capital preservation.
        Higher limits indicate Pinnacle's market confidence is mature; we scale into edge aggressively.
        """
        b = price - 1.0
        p = model_prob
        q = 1.0 - p
        full_kelly = (b * p - q) / b if b > 0 else 0
        if full_kelly <= 0:
            return 0.0, 0.0

        # Quarter-Kelly baseline
        quarter_kelly_pct = full_kelly * 0.25
        # Cap at 4% of vault maximum per wager
        quarter_kelly_pct = min(quarter_kelly_pct, 0.04)
        
        target_stake = bankroll * quarter_kelly_pct
        # Never exceed 30% of Pinnacle's live limit to stay beneath bookmaker radar and slippage
        max_market_allowed = limit_usd * 0.30
        final_stake = min(target_stake, max_market_allowed)
        
        return round(final_stake, 2), round(final_stake / bankroll, 4)

class PinnacleDataFeedSimulator:
    """
    Simulates high-velocity Pinnacle Guest Lines & Limits Feed
    Replicating JSON responses from:
    - /v2/fixtures
    - /v2/odds
    - /v1/line (live limits & overrounds)
    """
    def __init__(self):
        self.fixtures_template = [
            (1001, "Baseball", "MLB", "New York Yankees", "Boston Red Sox", "Gerrit Cole", "Brayan Bello", 0.158, 0.162, 0.178, 6.2, 4.05, 0.235),
            (1002, "Baseball", "MLB", "Atlanta Braves", "New York Mets", "Spencer Strider", "Kodai Senga", 0.188, 0.152, 0.192, 6.0, 4.02, 0.212),
            (1003, "Baseball", "MLB", "Toronto Blue Jays", "Baltimore Orioles", "Kevin Gausman", "Corbin Burnes", 0.154, 0.165, 0.180, 6.3, 4.08, 0.222),
            (1004, "Baseball", "MLB", "Los Angeles Dodgers", "San Francisco Giants", "Tyler Glasnow", "Logan Webb", 0.172, 0.158, 0.185, 6.1, 3.98, 0.242),
            (1005, "Baseball", "MLB", "Philadelphia Phillies", "San Diego Padres", "Zack Wheeler", "Dylan Cease", 0.145, 0.172, 0.176, 6.5, 3.92, 0.218),
            (1006, "Baseball", "MLB", "Detroit Tigers", "Cleveland Guardians", "Tarik Skubal", "Tanner Bibee", 0.164, 0.168, 0.182, 6.4, 3.95, 0.210)
        ]

    def seed_initial_state(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        
        for f in self.fixtures_template:
            fid, sport, lg, home, away, p_home, p_away = f[0], f[1], f[2], f[3], f[4], f[5], f[6]
            c.execute("""
            INSERT OR REPLACE INTO pinnacle_fixtures 
            (fixture_id, sport, league, home_team, away_team, event_time, status, pitcher_home, pitcher_away, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', '+2 hours'), 'PREMATCH', ?, ?, ?)
            """, (fid, sport, lg, home, away, p_home, p_away, now_iso))
        conn.commit()
        conn.close()

    def run_market_tick(self):
        """Generates real-time price changes, steam drops, and limits."""
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        c = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        q_engine = PinnacleQuantitativeEngine()

        c.execute("SELECT total_balance, available_cash FROM vault_account WHERE id = 1")
        v_row = c.fetchone()
        bankroll = v_row[0]
        cash = v_row[1]

        signals_detected = 0

        for f in self.fixtures_template:
            fid = f[0]
            pitcher = f[5] # Home starter
            sw, lk, fl, ip, bf, opp_k = f[7], f[8], f[9], f[10], f[11], f[12]
            
            # Model true Poisson lambda
            lam = q_engine.calculate_mack_lambda(sw, lk, fl, opp_k, ip, bf)
            prop_line = round(lam) + 0.5

            # Simulate Pinnacle 2-way pricing on Over/Under
            # Pinnacle lines operate on tiny margins (2.1% - 3.2% overround)
            base_over_price = round(random.choice([1.88, 1.91, 1.94, 2.02, 2.06, 2.12]), 2)
            # Corresponding reciprocal price with ~2.5% juice
            recip = 1.0 / (1.025 - (1.0 / base_over_price))
            base_under_price = round(max(1.70, recip + random.uniform(-0.02, 0.02)), 2)

            # Pinnacle limits: Tier 1 ($2,500), Tier 2 ($8,000), Tier 3 Game-Time Max ($20,000)
            limit_usd = random.choice([2500.0, 5000.0, 10000.0, 20000.0])
            tier = "MAX_CONFIDENCE ($20K)" if limit_usd >= 15000 else ("HIGH_LIMIT ($10K)" if limit_usd >= 8000 else "STANDARD ($2.5K-$5K)")

            # De-vig via Power Method
            fair_p_over, fair_p_under, vig = q_engine.devig_two_way_power(base_over_price, base_under_price)

            # Model Probabilities
            model_p_over = q_engine.price_poisson_tail(lam, prop_line, "Over")
            model_p_under = 1.0 - model_p_over

            sides_data = [
                ("Over", base_over_price, fair_p_over, model_p_over),
                ("Under", base_under_price, fair_p_under, model_p_under)
            ]

            for side, price, devig_prob, m_prob in sides_data:
                line_id = f"PINN-{fid}-K-{side[0]}-{int(prop_line*10)}"
                
                # Check previous price for steam / dropping odds
                c.execute("SELECT pinnacle_price, limit_usd FROM pinnacle_market_lines WHERE line_id = ?", (line_id,))
                prev_row = c.fetchone()
                prev_price = prev_row[0] if prev_row else price
                price_delta = ((price / prev_price) - 1.0) if prev_price > 0 else 0.0

                # Edge EV% against Pinnacle's posted decimal price
                ev_pct = (m_prob * price) - 1.0
                
                # Signal Categorization
                if ev_pct >= 0.040 and limit_usd >= 5000:
                    sig = "PULVERIZE (+EV HIGH-LIMIT SNIPE)"
                elif ev_pct >= 0.030:
                    sig = "STEAM_BUY (+EV OPPORTUNITY)"
                elif ev_pct <= -0.020:
                    sig = "FADE_NEGATIVE_EV"
                else:
                    sig = "MARKET_EFFICIENT_PASS"

                c.execute("""
                INSERT OR REPLACE INTO pinnacle_market_lines (
                    line_id, fixture_id, market_type, period, line_value, side,
                    pinnacle_price, prev_price, price_delta_pct, limit_usd, limit_tier,
                    overround, true_fair_odds, true_fair_prob, model_prob, edge_ev_pct, signal, updated_at
                ) VALUES (?, ?, 'Pitcher Strikeouts', 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    line_id, fid, prop_line, side, price, prev_price, price_delta,
                    limit_usd, tier, vig, round(1.0/devig_prob, 2), devig_prob,
                    m_prob, ev_pct, sig, now_iso
                ))

                # Log tick if price shifted
                if abs(price_delta) > 0.02:
                    c.execute("""
                    INSERT INTO line_movement_ticks (line_id, timestamp, price, limit_usd, event_type)
                    VALUES (?, ?, ?, ?, ?)
                    """, (line_id, now_iso, price, limit_usd, "STEAM_DROP" if price_delta < 0 else "LINE_DRIFT"))

                # Automated Stark Syndicate Execution Engine
                if ("PULVERIZE" in sig or "STEAM_BUY" in sig) and ev_pct >= 0.035:
                    c.execute("SELECT order_id FROM execution_orders WHERE line_id = ? AND status = 'EXECUTED'", (line_id,))
                    if not c.fetchone():
                        stake, stake_pct = q_engine.limit_weighted_kelly(bankroll, m_prob, price, limit_usd)
                        if stake >= 25.0 and cash >= stake:
                            order_id = f"ORD-{int(time.time()*1000)%10000000}-{random.randint(100,999)}"
                            fixture_str = f"{f[3]} vs {f[4]} ({pitcher})"
                            sel_str = f"{side} {prop_line} Strikeouts"

                            c.execute("""
                            INSERT INTO execution_orders (
                                order_id, line_id, placed_at, fixture_name, selection,
                                market_type, entry_price, limit_usd, order_size_usd, bankroll_pct, status
                            ) VALUES (?, ?, ?, ?, ?, 'Pitcher Strikeouts', ?, ?, ?, ?, 'EXECUTED')
                            """, (order_id, line_id, now_iso, fixture_str, sel_str, price, limit_usd, stake, stake_pct))

                            # Update vault balance
                            cash -= stake
                            c.execute("""
                            UPDATE vault_account SET available_cash = ?, allocated_in_flight = allocated_in_flight + ?, updated_at = ?
                            WHERE id = 1
                            """, (cash, stake, now_iso))

                            c.execute("""
                            INSERT INTO terminal_logs (timestamp, severity, module, message)
                            VALUES (?, 'HIGH_CONVICTION', 'EXECUTION_SNIPER', ?)
                            """, (now_iso, f"SNIPED PINNACLE LIMIT: {fixture_str} | {sel_str} @ {price} | Limit: ${limit_usd:,.0f} | Stake: ${stake:,.2f} ({stake_pct*100:.1f}%) | EV: +{ev_pct*100:.1f}%"))
                            signals_detected += 1

        conn.commit()
        conn.close()
        return signals_detected

    def run_settlement_and_clv_cycle(self):
        """Simulates Pinnacle line close, computes Closing Line Value (CLV%), and settles games."""
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        c = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()

        c.execute("""
        SELECT o.order_id, o.line_id, o.entry_price, o.order_size_usd, m.line_value, m.side, m.model_prob
        FROM execution_orders o
        JOIN pinnacle_market_lines m ON o.line_id = m.line_id
        WHERE o.status = 'EXECUTED'
        """)
        active_orders = c.fetchall()

        for ord_row in active_orders:
            order_id, line_id, entry_price, stake, line, side, m_prob = ord_row
            
            # Efficient Pinnacle Closing Line converges towards true fair probability + tiny residual noise
            fair_odds = 1.0 / m_prob
            closing_price = round(entry_price + (fair_odds - entry_price) * 0.75 + random.uniform(-0.03, 0.03), 2)
            closing_price = max(1.15, closing_price)
            clv_pct = round((entry_price / closing_price) - 1.0, 4)

            # Realize Poisson outcome
            # derive lambda from line value
            sim_lambda = line
            actual_k = np.random.poisson(sim_lambda)

            win = (side == "Over" and actual_k > line) or (side == "Under" and actual_k < line)
            outcome = 1 if win else 0
            pnl = round(stake * (entry_price - 1.0), 2) if win else -round(stake, 2)

            c.execute("""
            UPDATE execution_orders SET
                closing_price = ?,
                clv_pct = ?,
                actual_count = ?,
                outcome = ?,
                pnl_usd = ?,
                status = 'SETTLED'
            WHERE order_id = ?
            """, (closing_price, clv_pct, actual_k, outcome, pnl, order_id))

            # Update Vault Capital & High Water Mark
            c.execute("""
            UPDATE vault_account SET
                total_balance = total_balance + ?,
                available_cash = available_cash + ? + ?,
                allocated_in_flight = allocated_in_flight - ?,
                high_water_mark = MAX(high_water_mark, total_balance + ?),
                updated_at = ?
            WHERE id = 1
            """, (pnl, stake, pnl, stake, pnl, now_iso))

            c.execute("""
            INSERT INTO terminal_logs (timestamp, severity, module, message)
            VALUES (?, 'SETTLEMENT', 'CLEARING_HOUSE', ?)
            """, (now_iso, f"SETTLED {order_id}: Result={actual_k} Ks ({'WON' if win else 'LOST'}) | PnL: {'+' if pnl>=0 else ''}${pnl:,.2f} | CLV: {'+' if clv_pct>=0 else ''}{clv_pct*100:.2f}%"))

        conn.commit()
        conn.close()

if __name__ == "__main__":
    feed = PinnacleDataFeedSimulator()
    feed.seed_initial_state()
    snipes = feed.run_market_tick()
    print(f"Pinnacle High-Frequency Scan completed. Executed {snipes} limit-weighted snipes.")
