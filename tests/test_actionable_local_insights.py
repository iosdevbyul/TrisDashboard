import json
from datetime import date, datetime, timezone

from backend.agenda import load_agenda
from backend.fitness import load_fitness
from backend.dividends import load_dividends
from backend.portfolio import load_portfolio


def _write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_agenda_daily_counts_include_empty_days(tmp_path):
    path = _write(tmp_path, "agenda.json", {"events": [
        {"date": "2026-11-09", "title": "Meeting"},
        {"date": "2026-11-11", "title": "Run"},
        {"date": "2026-11-20", "title": "Later"}]})
    result = load_agenda(path, today=date(2026, 11, 9))
    assert len(result["next_seven_daily_counts"]) == 7
    assert [item["events"] for item in result["next_seven_daily_counts"]] == [1, 0, 1, 0, 0, 0, 0]


def test_workout_last_day_is_bounded_to_week(tmp_path):
    path = _write(tmp_path, "fitness.json", {"workouts": [
        {"date": "2026-10-01", "type": "walking", "duration_minutes": 15},
        {"date": "2026-11-07", "type": "running", "duration_minutes": 45}]})
    assert load_fitness(path, today=date(2026, 11, 9))["days_since_last_workout_in_week"] == 2
    path = _write(tmp_path, "fitness.json", {"workouts": [
        {"date": "2026-10-01", "type": "walking", "duration_minutes": 15}]})
    assert load_fitness(path, today=date(2026, 11, 9))["days_since_last_workout_in_week"] is None


def test_last_confirmed_payment_does_not_predict_future(tmp_path):
    path = _write(tmp_path, "dividends.json", {"payments": [
        {"symbol": "JEPQ", "currency": "USD", "paid_on": "2026-10-02", "amount": "4"},
        {"symbol": "SCHD", "currency": "USD", "paid_on": "2026-11-04", "amount": "6"}]})
    result = load_dividends(path, today=date(2026, 11, 9))
    assert result["last_confirmed_payment"] == {
        "symbol": "SCHD", "currency": "USD", "paid_on": "2026-11-04", "amount": "6"}
    empty = _write(tmp_path, "empty.json", {"payments": []})
    assert load_dividends(empty, today=date(2026, 11, 9))["last_confirmed_payment"] is None


def test_zero_quantity_symbols_are_separate_by_currency(tmp_path):
    path = _write(tmp_path, "portfolio.json", {"as_of": datetime.now(timezone.utc).isoformat(),
        "positions": [
            {"symbol": "jepq", "currency": "USD", "quantity": 0, "price": "50"},
            {"symbol": "SCHD", "currency": "USD", "quantity": 10},
            {"symbol": "005930", "currency": "KRW", "quantity": 0}]})
    result = load_portfolio(path)
    assert result["zero_quantity_symbols_by_currency"] == {"KRW": ["005930"], "USD": ["JEPQ"]}
