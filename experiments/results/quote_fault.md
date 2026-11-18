# quote fault

**Fault injected:** 2s service delay on `quote` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | shipping | 0.358978 | 0.473079 |
| 2 | frontend | 0.305696 | 0.000000 |
| 3 | checkout | 0.180153 | 0.057474 |
| 4 | **quote** | 0.155173 | 0.323272 |
| 5 | otel-collector-agent | 0.000000 | 0.000000 |
| 6 | flagd | 0.000000 | 0.000000 |
| 7 | email | 0.000000 | 0.000000 |
| 8 | currency | 0.000000 | 0.000000 |
| 9 | cart | 0.000000 | 0.000000 |
| 10 | payment | 0.000000 | 0.000000 |
| 11 | product-catalog | 0.000000 | 0.000000 |
| 12 | kafka | 0.000000 | 0.000000 |

| Metric | Result |
|--------|:------:|
| Top-1 | no |
| Top-3 | no |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | shipping | 0.70 |
| 2 | **quote** | 0.20 |
| 3 | recommendation | 0.06 |
| 4 | checkout | 0.02 |
| 5 | frontend | 0.02 |
| 6 | ad | 0.00 |
| 7 | cart | 0.00 |
| 8 | currency | 0.00 |
| 9 | email | 0.00 |
| 10 | image_provider | 0.00 |
| 11 | payment | 0.00 |
| 12 | product_catalog | 0.00 |

| Metric | Result |
|--------|:------:|
| Top-1 | no |
| Top-3 | yes |
