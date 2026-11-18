# cart fault

**Fault injected:** 2s service delay on `cart` service using `faults/inject-delay.sh`

## MicroRCA ranking

| Rank | Service | PPR | AS |
|-----:|---------|----:|---:|
| 1 | frontend | 0.406357 | 0.000000 |
| 2 | checkout | 0.362492 | 0.407778 |
| 3 | **cart** | 0.231150 | 0.356695 |
| 4 | email | 0.000000 | 0.000000 |
| 5 | otel-collector-agent | 0.000000 | 0.000000 |
| 6 | currency | 0.000000 | 0.000000 |
| 7 | payment | 0.000000 | 0.000000 |
| 8 | product-catalog | 0.000000 | 0.000000 |
| 9 | kafka | 0.000000 | 0.000000 |
| 10 | shipping | 0.000000 | 0.000000 |
| 11 | valkey-cart | 0.000000 | 0.000000 |
| 12 | flagd | 0.000000 | 0.000000 |

| Metric | Result |
|--------|:------:|
| Top-1 | no |
| Top-3 | yes |

## Jev ranking

| Rank | Service | Score |
|-----:|---------|------:|
| 1 | **cart** | 0.66 |
| 2 | recommendation | 0.19 |
| 3 | frontend | 0.09 |
| 4 | checkout | 0.05 |
| 5 | ad | 0.01 |
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
