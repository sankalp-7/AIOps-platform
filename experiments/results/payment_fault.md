# payment fault

**Fault injected:** 2s service delay on `payment` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | checkout | 0.415582 | 0.237126 |
| 2 | frontend | 0.353245 | 0.000000 |
| 3 | **payment** | 0.231173 | 0.250208 |
| 4 | otel-collector-agent | 0.000000 | 0.000000 |
| 5 | email | 0.000000 | 0.000000 |
| 6 | currency | 0.000000 | 0.000000 |
| 7 | cart | 0.000000 | 0.000000 |
| 8 | product-catalog | 0.000000 | 0.000000 |
| 9 | kafka | 0.000000 | 0.000000 |
| 10 | shipping | 0.000000 | 0.000000 |

| Metric | Result |
|--------|:------:|
| Top-1 | no |
| Top-3 | yes |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | **payment** | 0.40 |
| 2 | email | 0.16 |
| 3 | frontend | 0.16 |
| 4 | checkout | 0.13 |
| 5 | recommendation | 0.13 |
| 6 | ad | 0.01 |
| 7 | currency | 0.01 |
| 8 | cart | 0.00 |
| 9 | image_provider | 0.00 |
| 10 | product_catalog | 0.00 |
| 11 | quote | 0.00 |
| 12 | shipping | 0.00 |

| Metric | Result |
|--------|:------:|
| Top-1 | yes |
| Top-3 | yes |
