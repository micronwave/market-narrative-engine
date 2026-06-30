# Narrative Intelligence Platform — API Data Model

**Version:** Current

This document captures the active API payload shapes used by the frontend. It describes response contracts, not full database schema internals.

---

## Core Narrative Endpoints

- `GET /api/narratives` returns a list of visible narrative objects.
- `GET /api/narratives/{id}` returns one visible narrative object with expanded detail fields.

### VisibleNarrative (`GET /api/narratives`)

```json
{
  "id": "nar-001",
  "name": "Semiconductor Reshoring Acceleration",
  "descriptor": "US chip manufacturing policy is catalyzing supply-chain realignment.",
  "velocity_summary": "+14.0% signal velocity over 7d",
  "entropy": 0.72,
  "saturation": 0.45,
  "velocity_timeseries": [
    { "date": "2026-03-10", "value": 0.58 },
    { "date": "2026-03-11", "value": 0.62 }
  ],
  "signals": ["sig-001", "sig-002"],
  "catalysts": ["mut-010"],
  "mutations": ["mut-001", "mut-002"],
  "stage": "Growing",
  "burst_velocity": { "ratio": 3.2, "is_burst": true, "label": "RISING" },
  "topic_tags": ["regulatory", "macro"],
  "entity_tags": ["CHIPS Act", "TSMC"],
  "source_stats": { "total": 24, "news": 14, "research": 5, "filings": 3, "other": 2 },
  "last_evidence_at": "2026-05-01T13:45:00+00:00",
  "signal_direction": "bullish",
  "signal_confidence": 0.73,
  "signal_certainty": "expected",
  "signal_catalyst_type": "regulatory",
  "human_review_required": false,
  "blurred": false
}
```

### NarrativeDetail (`GET /api/narratives/{id}`)

`NarrativeDetail` extends `VisibleNarrative` with richer arrays and detail blocks:

```json
{
  "id": "nar-001",
  "name": "Semiconductor Reshoring Acceleration",
  "descriptor": "US chip manufacturing policy is catalyzing supply-chain realignment.",
  "velocity_summary": "+14.0% signal velocity over 7d",
  "entropy": 0.72,
  "saturation": 0.45,
  "velocity_timeseries": [{ "date": "2026-03-10", "value": 0.58 }],
  "signals": [
    {
      "id": "sig-001",
      "narrative_id": "nar-001",
      "headline": "Fab timeline moved up",
      "source": {
        "id": "src-001",
        "name": "Reuters",
        "type": "news",
        "url": "https://example.com/article",
        "credibility_score": 0.85
      },
      "timestamp": "2026-05-01T13:45:00+00:00",
      "sentiment": 0.2,
      "coordination_flag": false
    }
  ],
  "catalysts": [
    {
      "id": "mut-010",
      "narrative_id": "nar-001",
      "description": "Funding announcement",
      "timestamp": "2026-04-30T18:00:00+00:00",
      "impact_score": 0.82
    }
  ],
  "mutations": [
    {
      "id": "mut-001",
      "narrative_id": "nar-001",
      "from_state": "Emerging",
      "to_state": "Growing",
      "timestamp": "2026-04-29T00:00:00+00:00",
      "trigger": "mut-001",
      "description": "Narrative transitioned to growth stage."
    }
  ],
  "entropy_detail": {
    "narrative_id": "nar-001",
    "score": 0.72,
    "components": { "source_diversity": 0.65, "temporal_spread": 0.8, "sentiment_variance": 0.7 }
  },
  "assets": [],
  "sentiment": { "mean": 0.1, "min": -0.4, "max": 0.7, "std": 0.2, "count": 24, "polarization_label": "Moderate spread" },
  "signal": null,
  "coordination": null,
  "ns_score": 0.67,
  "document_count": 24,
  "cross_source_score": 0.42,
  "polarization": 0.2,
  "topic_tags": ["regulatory", "macro"],
  "burst_velocity": { "ratio": 3.2, "is_burst": true, "label": "RISING" },
  "blurred": false
}
```

---

## Related Narrative APIs

- `GET /api/narratives/{id}/assets`
- `GET /api/narratives/{id}/signal`
- `GET /api/narratives/{id}/history`
- `GET /api/narratives/{id}/manipulation`
- `GET /api/narratives/{id}/coordination`
- `GET /api/narratives/{id}/sources`
- `GET /api/narratives/{id}/documents`
- `GET /api/narratives/{id}/timeline`
- `GET /api/narratives/{id}/compare`
- `POST /api/narratives/{id}/export`
- `POST /api/narratives/{id}/analyze`

Companion graph/activity endpoints used by the same frontend surfaces:

- `GET /api/constellation`
- `GET /api/activity`

