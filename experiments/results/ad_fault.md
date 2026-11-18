# ad fault

**Fault injected:** 2s service delay on `ad` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | **ad** | 0.540541 | 0.226501 |
| 2 | frontend | 0.459459 | 0.000000 |
| 3 | otel-collector-agent | 0.000000 | 0.000000 |
| 4 | flagd | 0.000000 | 0.000000 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | **ad** | 0.67 |
| 2 | frontend | 0.18 |
| 3 | recommendation | 0.15 |
| 4 | cart | 0.00 |
| 5 | checkout | 0.00 |
| 6 | currency | 0.00 |
| 7 | email | 0.00 |
| 8 | image_provider | 0.00 |
| 9 | payment | 0.00 |
| 10 | product_catalog | 0.00 |
| 11 | quote | 0.00 |
| 12 | shipping | 0.00 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |
