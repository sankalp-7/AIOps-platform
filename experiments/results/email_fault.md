Fault injected - 2s service delay on email service using faults/inject-delay.sh

MicroRCA ranking:
 1. checkout                  PPR=0.369744 AS=0.094523
 2. email                     PPR=0.315973 AS=0.295220
 3. frontend                  PPR=0.314283 AS=0.000000
 4. otel-collector-agent      PPR=0.000000 AS=0.000000
 5. currency                  PPR=0.000000 AS=0.000000
 6. cart                      PPR=0.000000 AS=0.000000
 7. payment                   PPR=0.000000 AS=0.000000
 8. product-catalog           PPR=0.000000 AS=0.000000
 9. kafka                     PPR=0.000000 AS=0.000000
10. shipping                  PPR=0.000000 AS=0.000000
11. flagd                     PPR=0.000000 AS=0.000000

top-1: no

top-3: yes




Jev ranking:
{'ad': 0.01, 'cart': 0.0, 'checkout': 0.11, 'currency': 0.0, 'email': 0.38, 'frontend': 0.17, 'image_provider': 0.01, 'payment': 0.0, 'product_catalog': 0.0, 'quote': 0.0, 'recommendation': 0.13, 'shipping': 0.19}

top-1: yes

top-3: yes