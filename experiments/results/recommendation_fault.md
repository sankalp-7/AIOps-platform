# recommendation fault

**Fault injected:** 2s service delay on `recommendation` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | **recommendation** | 0.540541 | 0.328788 |
| 2 | frontend | 0.459459 | 0.000000 |
| 3 | otel-collector-agent | 0.000000 | 0.000000 |
| 4 | product-catalog | 0.000000 | 0.000000 |
| 5 | flagd | 0.000000 | 0.000000 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | **recommendation** | 0.84 |
| 2 | frontend | 0.13 |
| 3 | checkout | 0.01 |
| 4 | payment | 0.01 |
| 5 | product_catalog | 0.01 |
| 6 | ad | 0.00 |
| 7 | cart | 0.00 |
| 8 | currency | 0.00 |
| 9 | email | 0.00 |
| 10 | image_provider | 0.00 |
| 11 | quote | 0.00 |
| 12 | shipping | 0.00 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |
