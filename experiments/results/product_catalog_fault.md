Fault injected - 2s service delay on product_catalog service using faults/inject-delay.sh

MicroRCA ranking:
 1. frontend                  PPR=0.396766 AS=0.000000
 2. recommendation            PPR=0.255249 AS=0.513544
 3. product-catalog           PPR=0.204677 AS=0.532861
 4. checkout                  PPR=0.143308 AS=0.222113
 5. otel-collector-agent      PPR=0.000000 AS=0.000000
 6. flagd                     PPR=0.000000 AS=0.000000
 7. astronomy-db              PPR=0.000000 AS=0.000000
 8. email                     PPR=0.000000 AS=0.000000
 9. currency                  PPR=0.000000 AS=0.000000
10. cart                      PPR=0.000000 AS=0.000000
11. payment                   PPR=0.000000 AS=0.000000
12. kafka                     PPR=0.000000 AS=0.000000
13. shipping                  PPR=0.000000 AS=0.000000

top-1: no

top-3: yes




Jev ranking:
{'ad': 0.0, 'cart': 0.0, 'checkout': 0.01, 'currency': 0.0, 'email': 0.0, 'frontend': 0.03, 'image_provider': 0.0, 'payment': 0.0, 'product_catalog': 0.47, 'quote': 0.0, 'recommendation': 0.49, 'shipping': 0.0}

top-1: no

top-3: yes