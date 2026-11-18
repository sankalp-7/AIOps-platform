# checkout fault

**Fault injected:** 2s service delay on `checkout` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | **checkout** | 0.540541 | 0.046904 |
| 2 | frontend | 0.459459 | 0.000000 |
| 3 | email | 0.000000 | 0.000000 |
| 4 | otel-collector-agent | 0.000000 | 0.000000 |
| 5 | currency | 0.000000 | 0.000000 |
| 6 | cart | 0.000000 | 0.000000 |
| 7 | payment | 0.000000 | 0.000000 |
| 8 | product-catalog | 0.000000 | 0.000000 |
| 9 | kafka | 0.000000 | 0.000000 |
| 10 | shipping | 0.000000 | 0.000000 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | **checkout** | 0.48 |
| 2 | frontend | 0.37 |
| 3 | recommendation | 0.13 |
| 4 | ad | 0.01 |
| 5 | product_catalog | 0.01 |
| 6 | cart | 0.00 |
| 7 | currency | 0.00 |
| 8 | email | 0.00 |
| 9 | image_provider | 0.00 |
| 10 | payment | 0.00 |
| 11 | quote | 0.00 |
| 12 | shipping | 0.00 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |
