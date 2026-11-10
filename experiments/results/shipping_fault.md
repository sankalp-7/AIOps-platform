Fault injected - 2s service delay on shipping service using faults/inject-delay.sh

MicroRCA Ranking:
 1. frontend                  PPR=0.408060 AS=0.000000
 2. checkout                  PPR=0.392656 AS=0.607377
 3. shipping                  PPR=0.199284 AS=0.406768
 4. quote                     PPR=0.000000 AS=0.000000
 5. otel-collector-agent      PPR=0.000000 AS=0.000000
 6. flagd                     PPR=0.000000 AS=0.000000
 7. email                     PPR=0.000000 AS=0.000000
 8. currency                  PPR=0.000000 AS=0.000000
 9. cart                      PPR=0.000000 AS=0.000000
10. payment                   PPR=0.000000 AS=0.000000
11. product-catalog           PPR=0.000000 AS=0.000000
12. kafka                     PPR=0.000000 AS=0.000000

top-3: yes

top-1: no



Jev Ranking:
{'ad': 0.0, 'cart': 0.0, 'checkout': 0.09, 'currency': 0.0, 'email': 0.0, 'frontend': 0.35, 'image_provider': 0.01, 'payment': 0.01, 'product_catalog': 0.0, 'quote': 0.01, 'recommendation': 0.12, 'shipping': 0.41}

top-3: yes

top-1: yes