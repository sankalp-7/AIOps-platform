Fault injected - 2s service delay on quote service using faults/inject-delay.sh

MicroRCA ranking:
 1. shipping                  PPR=0.358978 AS=0.473079
 2. frontend                  PPR=0.305696 AS=0.000000
 3. checkout                  PPR=0.180153 AS=0.057474
 4. quote                     PPR=0.155173 AS=0.323272
 5. otel-collector-agent      PPR=0.000000 AS=0.000000
 6. flagd                     PPR=0.000000 AS=0.000000
 7. email                     PPR=0.000000 AS=0.000000
 8. currency                  PPR=0.000000 AS=0.000000
 9. cart                      PPR=0.000000 AS=0.000000
10. payment                   PPR=0.000000 AS=0.000000
11. product-catalog           PPR=0.000000 AS=0.000000
12. kafka                     PPR=0.000000 AS=0.000000

top-1: no

top-3: no




Jev ranking:
{'ad': 0.0, 'cart': 0.0, 'checkout': 0.02, 'currency': 0.0, 'email': 0.0, 'frontend': 0.02, 'image_provider': 0.0, 'payment': 0.0, 'product_catalog': 0.0, 'quote': 0.2, 'recommendation': 0.06, 'shipping': 0.7}

top-1: no

top-3: yes