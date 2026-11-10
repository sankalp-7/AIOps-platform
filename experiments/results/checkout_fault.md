Fault injected - 2s service delay on checkout service using faults/inject-delay.sh

MicroRCA ranking:
 1. checkout                  PPR=0.540541 AS=0.046904
 2. frontend                  PPR=0.459459 AS=0.000000
 3. email                     PPR=0.000000 AS=0.000000
 4. otel-collector-agent      PPR=0.000000 AS=0.000000
 5. currency                  PPR=0.000000 AS=0.000000
 6. cart                      PPR=0.000000 AS=0.000000
 7. payment                   PPR=0.000000 AS=0.000000
 8. product-catalog           PPR=0.000000 AS=0.000000
 9. kafka                     PPR=0.000000 AS=0.000000
10. shipping                  PPR=0.000000 AS=0.000000

top-1: yes

top-3: yes




Jev ranking:
{'ad': 0.01, 'cart': 0.0, 'checkout': 0.48, 'currency': 0.0, 'email': 0.0, 'frontend': 0.37, 'image_provider': 0.0, 'payment': 0.0, 'product_catalog': 0.01, 'quote': 0.0, 'recommendation': 0.13, 'shipping': 0.0}

top-1: yes

top-3: yes