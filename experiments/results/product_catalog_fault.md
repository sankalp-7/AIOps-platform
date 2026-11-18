# product_catalog fault

**Fault injected:** 2s service delay on `product_catalog` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | frontend | 0.396766 | 0.000000 |
| 2 | recommendation | 0.255249 | 0.513544 |
| 3 | **product-catalog** | 0.204677 | 0.532861 |
| 4 | checkout | 0.143308 | 0.222113 |
| 5 | otel-collector-agent | 0.000000 | 0.000000 |
| 6 | flagd | 0.000000 | 0.000000 |
| 7 | astronomy-db | 0.000000 | 0.000000 |
| 8 | email | 0.000000 | 0.000000 |
| 9 | currency | 0.000000 | 0.000000 |
| 10 | cart | 0.000000 | 0.000000 |
| 11 | payment | 0.000000 | 0.000000 |
| 12 | kafka | 0.000000 | 0.000000 |
| 13 | shipping | 0.000000 | 0.000000 |

| Metric | Result |
|--------|:------:|
| Top-1 | no |
| Top-3 | yes |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | recommendation | 0.49 |
| 2 | **product_catalog** | 0.47 |
| 3 | frontend | 0.03 |
| 4 | checkout | 0.01 |
| 5 | ad | 0.00 |
| 6 | cart | 0.00 |
| 7 | currency | 0.00 |
| 8 | email | 0.00 |
| 9 | image_provider | 0.00 |
| 10 | payment | 0.00 |
| 11 | quote | 0.00 |
| 12 | shipping | 0.00 |

| Metric | Result |
|--------|:------:|
| Top-1 | no |
| Top-3 | yes |
