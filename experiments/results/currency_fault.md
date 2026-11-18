# currency fault

**Fault injected:** 2s service delay on `currency` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | frontend | 0.417505 | 0.000000 |
| 2 | checkout | 0.399869 | 0.666230 |
| 3 | **currency** | 0.182626 | 0.377562 |
| 4 | email | 0.000000 | 0.000000 |
| 5 | otel-collector-agent | 0.000000 | 0.000000 |
| 6 | cart | 0.000000 | 0.000000 |
| 7 | payment | 0.000000 | 0.000000 |
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
| 1 | **currency** | 0.80 |
| 2 | recommendation | 0.09 |
| 3 | checkout | 0.06 |
| 4 | frontend | 0.04 |
| 5 | ad | 0.01 |
| 6 | cart | 0.00 |
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
