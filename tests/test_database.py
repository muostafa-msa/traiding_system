from __future__ import annotations

from datetime import datetime, timezone, timedelta

from storage.database import Database
from core.types import TradeSignal, NewsItem


def _make_news_item(
    headline: str = "Gold prices surge", source: str = "test"
) -> NewsItem:
    return NewsItem(
        source=source,
        headline=headline,
        url="https://example.com/article",
        published_at=datetime.now(timezone.utc),
        raw_text="",
    )


class TestSaveAndGetSignal:
    def test_save_signal_returns_id(self, db: Database, sample_buy_signal: TradeSignal):
        signal_id = db.save_signal(sample_buy_signal, "approved")
        assert signal_id == 1

    def test_save_multiple_signals_increments_id(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        id1 = db.save_signal(sample_buy_signal, "approved")
        id2 = db.save_signal(sample_buy_signal, "rejected")
        assert id1 == 1
        assert id2 == 2

    def test_get_last_signal_returns_most_recent(
        self,
        db: Database,
        sample_buy_signal: TradeSignal,
        sample_sell_signal: TradeSignal,
    ):
        db.save_signal(sample_buy_signal, "approved")
        db.save_signal(sample_sell_signal, "rejected")
        result = db.get_last_signal("XAU/USD")
        assert result is not None
        assert result["direction"] == "SELL"
        assert result["status"] == "rejected"

    def test_get_last_signal_returns_none_when_empty(self, db: Database):
        result = db.get_last_signal("XAU/USD")
        assert result is None

    def test_get_last_signal_filters_by_asset(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        db.save_signal(sample_buy_signal, "approved")
        result = db.get_last_signal("EUR/USD")
        assert result is None

    def test_save_signal_stores_all_fields(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        db.save_signal(sample_buy_signal, "approved")
        result = db.get_last_signal("XAU/USD")
        assert result["asset"] == "XAU/USD"
        assert result["direction"] == "BUY"
        assert result["entry_price"] == 2350.0
        assert result["stop_loss"] == 2335.0
        assert result["take_profit"] == 2380.0
        assert result["probability"] == 0.85
        assert result["timeframe"] == "1h"
        assert result["reasoning"] == "Strong bullish momentum"
        assert result["status"] == "approved"


class TestOpenCloseTrade:
    def test_open_trade_returns_id(self, db: Database, sample_buy_signal: TradeSignal):
        signal_id = db.save_signal(sample_buy_signal, "approved")
        trade_id = db.open_trade(signal_id, 0.1, 2350.0)
        assert trade_id == 1

    def test_open_trade_incrementing_ids(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        signal_id = db.save_signal(sample_buy_signal, "approved")
        id1 = db.open_trade(signal_id, 0.1, 2350.0)
        id2 = db.open_trade(signal_id, 0.2, 2350.0)
        assert id1 == 1
        assert id2 == 2

    def test_close_trade_sets_exit_fields(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        signal_id = db.save_signal(sample_buy_signal, "approved")
        trade_id = db.open_trade(signal_id, 0.1, 2350.0)
        db.close_trade(trade_id, 2370.0, "tp_hit")
        count = db.get_open_positions_count()
        assert count == 0

    def test_get_open_positions_count_empty(self, db: Database):
        assert db.get_open_positions_count() == 0

    def test_get_open_positions_count_with_open_trades(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        signal_id = db.save_signal(sample_buy_signal, "approved")
        db.open_trade(signal_id, 0.1, 2350.0)
        db.open_trade(signal_id, 0.2, 2350.0)
        assert db.get_open_positions_count() == 2

    def test_get_open_positions_count_mixed(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        signal_id = db.save_signal(sample_buy_signal, "approved")
        t1 = db.open_trade(signal_id, 0.1, 2350.0)
        db.open_trade(signal_id, 0.2, 2350.0)
        db.close_trade(t1, 2360.0, "tp_hit")
        assert db.get_open_positions_count() == 1

    def test_get_daily_pnl_no_trades(self, db: Database):
        assert db.get_daily_pnl() == 0.0

    def test_get_daily_pnl_with_closed_trades(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        signal_id = db.save_signal(sample_buy_signal, "approved")
        t1 = db.open_trade(signal_id, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")
        pnl = db.get_daily_pnl()
        assert pnl == 2.0


class TestAccountState:
    def test_initial_account_state(self, db: Database):
        state = db.get_account_state()
        assert state.capital == 10000.0
        assert state.open_positions == 0
        assert state.daily_pnl == 0.0
        assert state.kill_switch_active is False

    def test_update_account_state_capital(self, db: Database):
        db.update_account_state(capital=9500.0)
        state = db.get_account_state()
        assert state.capital == 9500.0

    def test_update_account_state_kill_switch(self, db: Database):
        db.update_account_state(kill_switch_active=True)
        state = db.get_account_state()
        assert state.kill_switch_active is True

    def test_update_account_state_daily_pnl(self, db: Database):
        db.update_account_state(daily_pnl=-250.0)
        state = db.get_account_state()
        assert state.daily_pnl == -250.0

    def test_update_account_state_multiple_fields(self, db: Database):
        db.update_account_state(capital=9500.0, daily_pnl=-500.0, open_positions=1)
        state = db.get_account_state()
        assert state.capital == 9500.0
        assert state.daily_pnl == -500.0
        assert state.open_positions == 1

    def test_reset_daily_if_needed_same_day(self, db: Database):
        db.update_account_state(daily_pnl=-100.0, kill_switch_active=True)
        db.reset_daily_if_needed()
        state = db.get_account_state()
        assert state.daily_pnl == -100.0
        assert state.kill_switch_active is True

    def test_reset_daily_if_needed_new_day(self, db: Database):
        db.update_account_state(daily_pnl=-100.0, kill_switch_active=True)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        db.update_account_state(updated_at=yesterday.isoformat())
        db.reset_daily_if_needed()
        state = db.get_account_state()
        assert state.daily_pnl == 0.0
        assert state.kill_switch_active is False


class TestDailyPerformance:
    def test_get_daily_performance_empty(self, db: Database):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        perf = db.get_daily_performance(today)
        assert perf["total_signals"] == 0
        assert perf["trades_taken"] == 0
        assert perf["net_pnl"] == 0.0

    def test_update_daily_performance_creates_record(self, db: Database):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        db.update_daily_performance(
            today, total_signals=5, trades_taken=3, wins=2, losses=1, net_pnl=150.0
        )
        perf = db.get_daily_performance(today)
        assert perf["total_signals"] == 5
        assert perf["trades_taken"] == 3
        assert perf["wins"] == 2
        assert perf["losses"] == 1
        assert perf["net_pnl"] == 150.0

    def test_update_daily_performance_updates_existing(self, db: Database):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        db.update_daily_performance(today, total_signals=5, trades_taken=3)
        db.update_daily_performance(today, total_signals=10, trades_taken=6)
        perf = db.get_daily_performance(today)
        assert perf["total_signals"] == 10
        assert perf["trades_taken"] == 6

    def test_update_daily_performance_different_dates(self, db: Database):
        db.update_daily_performance("2026-01-15", total_signals=3, net_pnl=100.0)
        db.update_daily_performance("2026-01-16", total_signals=7, net_pnl=-50.0)
        perf1 = db.get_daily_performance("2026-01-15")
        perf2 = db.get_daily_performance("2026-01-16")
        assert perf1["total_signals"] == 3
        assert perf1["net_pnl"] == 100.0
        assert perf2["total_signals"] == 7
        assert perf2["net_pnl"] == -50.0


class TestSaveAndGetNews:
    def test_save_news_inserts_record(self, db: Database):
        item = _make_news_item("Gold prices surge")
        content_hash = "abc123"
        db.save_news(item, "Bullish", 0.95, content_hash)
        rows = db.get_recent_news(4)
        assert len(rows) == 1
        assert rows[0]["headline"] == "Gold prices surge"
        assert rows[0]["classification"] == "Bullish"
        assert rows[0]["confidence"] == 0.95

    def test_save_news_duplicate_hash_ignored(self, db: Database):
        item = _make_news_item("Gold prices surge")
        content_hash = "same_hash"
        db.save_news(item, "Bullish", 0.95, content_hash)
        db.save_news(item, "Bearish", 0.80, content_hash)
        rows = db.get_recent_news(4)
        assert len(rows) == 1
        assert rows[0]["classification"] == "Bullish"

    def test_get_recent_news_respects_window(self, db: Database):
        now = datetime.now(timezone.utc)
        old_item = NewsItem(
            source="test",
            headline="Old news",
            url="",
            published_at=now - timedelta(hours=5),
            raw_text="",
        )
        new_item = NewsItem(
            source="test",
            headline="New news",
            url="",
            published_at=now - timedelta(hours=1),
            raw_text="",
        )
        db.save_news(old_item, "Neutral", 0.6, "hash_old")
        old_collected = (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        db._conn.execute(
            "UPDATE news SET collected_at = ? WHERE content_hash = ?",
            (old_collected, "hash_old"),
        )
        db._conn.commit()
        db.save_news(new_item, "Bullish", 0.9, "hash_new")
        rows = db.get_recent_news(4)
        assert len(rows) == 1
        assert rows[0]["headline"] == "New news"

    def test_get_recent_news_returns_empty_when_none(self, db: Database):
        rows = db.get_recent_news(4)
        assert rows == []


class TestCheckHashExists:
    def test_check_hash_exists_returns_false_for_unknown(self, db: Database):
        assert db.check_hash_exists("nonexistent") is False

    def test_check_hash_exists_returns_true_after_save(self, db: Database):
        item = _make_news_item("Gold prices surge")
        db.save_news(item, "Bullish", 0.95, "known_hash")
        assert db.check_hash_exists("known_hash") is True

    def test_check_hash_exists_is_case_sensitive(self, db: Database):
        item = _make_news_item("Gold prices surge")
        db.save_news(item, "Bullish", 0.95, "Hash_ABC")
        assert db.check_hash_exists("Hash_ABC") is True
        assert db.check_hash_exists("hash_abc") is False


class TestBlackout:
    def test_initial_blackout_not_active(self, db: Database):
        assert db.is_blackout_active() is False

    def test_set_blackout_until_activates(self, db: Database):
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        db.set_blackout_until(future)
        assert db.is_blackout_active() is True

    def test_blackout_expired_is_not_active(self, db: Database):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        db.set_blackout_until(past)
        assert db.is_blackout_active() is False

    def test_clear_expired_blackout_clears_past(self, db: Database):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        db.set_blackout_until(past)
        db.clear_expired_blackout()
        row = db._conn.execute(
            "SELECT blackout_until FROM account_state ORDER BY id LIMIT 1"
        ).fetchone()
        assert row["blackout_until"] is None

    def test_clear_expired_blackout_keeps_active(self, db: Database):
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        db.set_blackout_until(future)
        db.clear_expired_blackout()
        assert db.is_blackout_active() is True


class TestSharpeRatio:
    def test_sharpe_empty_returns_zero(self, db: Database):
        assert db._compute_sharpe_ratio([]) == 0.0

    def test_sharpe_single_value_returns_zero(self, db: Database):
        assert db._compute_sharpe_ratio([0.05]) == 0.0

    def test_sharpe_mixed_values(self, db: Database):
        returns = [0.01, -0.005, 0.02, -0.01, 0.015]
        result = db._compute_sharpe_ratio(returns)
        assert result > 0.0

    def test_sharpe_all_same_returns_zero(self, db: Database):
        returns = [0.01, 0.01, 0.01]
        assert db._compute_sharpe_ratio(returns) == 0.0


class TestPerformanceSummary:
    def test_empty_trades_all_zeros(self, db: Database):
        summary = db.get_performance_summary("daily")
        assert summary["total_trades"] == 0
        assert summary["total_signals"] == 0
        assert summary["wins"] == 0
        assert summary["losses"] == 0
        assert summary["win_rate"] == 0.0
        assert summary["net_pnl"] == 0.0
        assert summary["sharpe_ratio"] == 0.0
        assert summary["profit_factor"] == 0.0

    def test_single_trade_sharpe_zero(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        sid = db.save_signal(sample_buy_signal, "approved")
        tid = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(tid, 2370.0, "tp_hit")
        summary = db.get_performance_summary("daily")
        assert summary["sharpe_ratio"] == 0.0

    def test_mixed_wins_losses(self, db: Database, sample_buy_signal: TradeSignal):
        sid = db.save_signal(sample_buy_signal, "approved")
        t1 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")
        t2 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t2, 2330.0, "sl_hit")
        t3 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t3, 2380.0, "tp_hit")
        summary = db.get_performance_summary("daily")
        assert summary["total_trades"] == 3
        assert summary["wins"] == 2
        assert summary["losses"] == 1
        assert summary["win_rate"] == 2 / 3
        assert summary["net_pnl"] > 0
        assert summary["sharpe_ratio"] > 0.0

    def test_all_wins_profit_factor_infinity(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        sid = db.save_signal(sample_buy_signal, "approved")
        t1 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")
        t2 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t2, 2380.0, "tp_hit")
        summary = db.get_performance_summary("daily")
        assert summary["profit_factor"] == float("inf")

    def test_breakeven_counted_as_loss(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        sid = db.save_signal(sample_buy_signal, "approved")
        tid = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(tid, 2350.0, "manual")
        summary = db.get_performance_summary("daily")
        assert summary["losses"] == 1
        assert summary["wins"] == 0


class TestMultiPeriodSummary:
    def test_daily_returns_only_today_trades(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        now = datetime.now(timezone.utc)
        sid = db.save_signal(sample_buy_signal, "approved")

        t1 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")

        yesterday = now - timedelta(days=1)
        t2 = db.open_trade(sid, 0.1, 2350.0)
        db._conn.execute(
            "UPDATE trades SET closed_at = ? WHERE id = ?",
            (yesterday.isoformat(), t2),
        )
        db._conn.commit()

        summary = db.get_performance_summary("daily")
        assert summary["total_trades"] == 1

    def test_weekly_returns_last_7_days(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        now = datetime.now(timezone.utc)
        sid = db.save_signal(sample_buy_signal, "approved")

        t1 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")

        three_days = now - timedelta(days=3)
        t2 = db.open_trade(sid, 0.1, 2350.0)
        db._conn.execute(
            "UPDATE trades SET closed_at = ? WHERE id = ?",
            (three_days.isoformat(), t2),
        )
        db._conn.commit()

        summary = db.get_performance_summary("weekly")
        assert summary["total_trades"] == 2

    def test_monthly_returns_last_30_days(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        now = datetime.now(timezone.utc)
        sid = db.save_signal(sample_buy_signal, "approved")

        t1 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")

        fifteen_days = now - timedelta(days=15)
        t2 = db.open_trade(sid, 0.1, 2350.0)
        db._conn.execute(
            "UPDATE trades SET closed_at = ? WHERE id = ?",
            (fifteen_days.isoformat(), t2),
        )
        db._conn.commit()

        forty_five_days = now - timedelta(days=45)
        t3 = db.open_trade(sid, 0.1, 2350.0)
        db._conn.execute(
            "UPDATE trades SET closed_at = ? WHERE id = ?",
            (forty_five_days.isoformat(), t3),
        )
        db._conn.commit()

        summary = db.get_performance_summary("monthly")
        assert summary["total_trades"] == 2

    def test_all_returns_everything(self, db: Database, sample_buy_signal: TradeSignal):
        now = datetime.now(timezone.utc)
        sid = db.save_signal(sample_buy_signal, "approved")

        t1 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")

        forty_five_days = now - timedelta(days=45)
        t2 = db.open_trade(sid, 0.1, 2350.0)
        db._conn.execute(
            "UPDATE trades SET closed_at = ? WHERE id = ?",
            (forty_five_days.isoformat(), t2),
        )
        db._conn.commit()

        summary = db.get_performance_summary("all")
        assert summary["total_trades"] == 2


class TestDrawdownAndReturn:
    def test_max_drawdown_no_trades(self, db: Database):
        assert db._compute_max_drawdown([], 10000.0) == 0.0

    def test_max_drawdown_steady_wins(self, db: Database):
        pnls = [100.0, 200.0, 150.0]
        assert db._compute_max_drawdown(pnls, 10000.0) == 0.0

    def test_max_drawdown_win_then_loss(self, db: Database):
        pnls = [500.0, -300.0]
        expected = (10500.0 - 10200.0) / 10500.0 * 100
        assert abs(db._compute_max_drawdown(pnls, 10000.0) - expected) < 0.01

    def test_max_drawdown_all_losses(self, db: Database):
        pnls = [-200.0, -300.0]
        expected = 500.0 / 10000.0 * 100
        assert abs(db._compute_max_drawdown(pnls, 10000.0) - expected) < 0.01

    def test_max_drawdown_zero_capital(self, db: Database):
        assert db._compute_max_drawdown([100.0], 0.0) == 0.0

    def test_total_return_equals_net_pnl_over_capital(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        sid = db.save_signal(sample_buy_signal, "approved")
        t1 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")
        summary = db.get_performance_summary("daily")
        expected_return = summary["net_pnl"] / 10000.0 * 100
        assert abs(summary["total_return"] - expected_return) < 0.01

    def test_no_trades_zero_return_and_drawdown(self, db: Database):
        summary = db.get_performance_summary("daily")
        assert summary["max_drawdown"] == 0.0
        assert summary["total_return"] == 0.0

    def test_summary_includes_drawdown_and_return(
        self, db: Database, sample_buy_signal: TradeSignal
    ):
        sid = db.save_signal(sample_buy_signal, "approved")
        t1 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t1, 2370.0, "tp_hit")
        t2 = db.open_trade(sid, 0.1, 2350.0)
        db.close_trade(t2, 2330.0, "sl_hit")
        summary = db.get_performance_summary("daily")
        assert "max_drawdown" in summary
        assert "total_return" in summary
        assert summary["max_drawdown"] > 0
        assert isinstance(summary["total_return"], float)
