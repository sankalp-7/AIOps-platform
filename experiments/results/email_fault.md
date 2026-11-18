# email fault

**Fault injected:** 2s service delay on `email` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | checkout | 0.369744 | 0.094523 |
| 2 | **email** | 0.315973 | 0.295220 |
| 3 | frontend | 0.314283 | 0.000000 |
| 4 | otel-collector-agent | 0.000000 | 0.000000 |
| 5 | currency | 0.000000 | 0.000000 |
| 6 | cart | 0.000000 | 0.000000 |
| 7 | payment | 0.000000 | 0.000000 |
| 8 | product-catalog | 0.000000 | 0.000000 |
| 9 | kafka | 0.000000 | 0.000000 |
| 10 | shipping | 0.000000 | 0.000000 |
| 11 | flagd | 0.000000 | 0.000000 |

| Metric | Result |
|--------|:------:|
| Top-1 | no |
| Top-3 | yes |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | **email** | 0.38 |
| 2 | shipping | 0.19 |
| 3 | frontend | 0.17 |
| 4 | recommendation | 0.13 |
| 5 | checkout | 0.11 |
| 6 | ad | 0.01 |
| 7 | image_provider | 0.01 |
| 8 | cart | 0.00 |
| 9 | currency | 0.00 |
| 10 | payment | 0.00 |
| 11 | product_catalog | 0.00 |
| 12 | quote | 0.00 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |
