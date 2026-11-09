import json
from datetime import date, datetime, timezone
from backend.agenda import load_agenda
from backend.fitness import load_fitness
from backend.dividends import load_dividends
from backend.portfolio import load_portfolio


def save(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_agenda_free_days(tmp_path):
    path = save(tmp_path, "a.json", {"events": [
        {"date":"2026-11-09","title":"Meeting"},
        {"date":"2026-11-10","title":"Call"},
        {"date":"2026-11-10","title":"Second call"}]})
    assert load_agenda(path, date(2026,11,9))["next_seven_free_days"] == 5
    assert load_agenda(save(tmp_path, "empty.json", {"events":[]}), date(2026,11,9))["next_seven_free_days"] == 7


def test_fitness_consecutive_rest_days(tmp_path):
    path = save(tmp_path, "f.json", {"workouts": [
        {"date":"2026-11-07","type":"running","duration_minutes":30}]})
    assert load_fitness(path, date(2026,11,9))["ongoing_rest_streak_days"] == 2
    assert load_fitness(save(tmp_path, "f2.json", {"workouts":[]}), date(2026,11,9))["ongoing_rest_streak_days"] == 7


def test_dividends_days_since_confirmed_payment(tmp_path):
    path = save(tmp_path, "d.json", {"payments": [
        {"symbol":"JEPQ","currency":"USD","paid_on":"2026-11-05","amount":"1"}]})
    assert load_dividends(path, date(2026,11,9))["days_since_last_confirmed_payment"] == 4
    assert load_dividends(save(tmp_path, "d2.json", {"payments":[]}), date(2026,11,9))["days_since_last_confirmed_payment"] is None


def test_portfolio_price_completeness(tmp_path):
    path = save(tmp_path, "p.json", {"as_of":datetime.now(timezone.utc).isoformat(),
        "positions":[
            {"symbol":"JEPQ","currency":"USD","quantity":1,"price":50},
            {"symbol":"SCHD","currency":"USD","quantity":1},
            {"symbol":"005930","currency":"KRW","quantity":1,"price":0}]})
    assert load_portfolio(path)["price_coverage_percent_by_currency"] == {"USD":50.0, "KRW":100.0}
