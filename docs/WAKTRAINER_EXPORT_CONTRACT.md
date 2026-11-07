# WakTrainer local export contract v1 (proposal)

This is a **TrisDashboard-defined interchange contract**, not a claim that the WakTrainer iOS app already exports this format. A separate WakTrainer feature or exporter must generate the file before automatic integration is possible.

## Top-level
```json
{
  "schema_version": 1,
  "sessions": [
    {
      "started_at": "2026-11-08T08:10:00+09:00",
      "activity_type": "running",
      "duration_seconds": 2700,
      "distance_meters": 7250
    }
  ]
}
```

- `started_at`: ISO 8601 with UTC offset. The original date at that offset is preserved for daily aggregation.
- `activity_type`: `running`, `walking`, `cycling`, `strength` or `climbing`.
- `duration_seconds`: finite non-negative seconds, at most 86400.
- `distance_meters`: optional finite non-negative meters, at most 1000000.
- maximum 500 sessions / 128 KiB JSON.
- Reject unknown schema versions, unknown workout types, impossible units and invalid timestamps.

The bridge converts these to the existing local fitness JSON format (minutes/kilometers). It performs no iOS permission requests, HealthKit reading, network upload or background synchronization. The app-side implementation remains a separate task.
