# shipping fault

**Fault injected:** 2s service delay on `shipping` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | frontend | 0.408060 | 0.000000 |
| 2 | checkout | 0.392656 | 0.607377 |
| 3 | **shipping** | 0.199284 | 0.406768 |
| 4 | quote | 0.000000 | 0.000000 |
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
| Top-3 | yes |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | **shipping** | 0.41 |
| 2 | frontend | 0.35 |
| 3 | recommendation | 0.12 |
| 4 | checkout | 0.09 |
| 5 | image_provider | 0.01 |
| 6 | payment | 0.01 |
| 7 | quote | 0.01 |
| 8 | ad | 0.00 |
| 9 | cart | 0.00 |
| 10 | currency | 0.00 |
| 11 | email | 0.00 |
| 12 | product_catalog | 0.00 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |
