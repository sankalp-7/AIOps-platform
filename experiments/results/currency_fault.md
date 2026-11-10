Fault injected - 2s service delay on currency service using faults/inject-delay.sh

MicroRCA ranking:
 1. frontend                  PPR=0.417505 AS=0.000000
 2. checkout                  PPR=0.399869 AS=0.666230
 3. currency                  PPR=0.182626 AS=0.377562
 4. email                     PPR=0.000000 AS=0.000000
 5. otel-collector-agent      PPR=0.000000 AS=0.000000
 6. cart                      PPR=0.000000 AS=0.000000
 7. payment                   PPR=0.000000 AS=0.000000
 8. product-catalog           PPR=0.000000 AS=0.000000
 9. kafka                     PPR=0.000000 AS=0.000000
10. shipping                  PPR=0.000000 AS=0.000000

top-1: no

top-3: yes




Jev ranking:
{'ad': 0.01, 'cart': 0.0, 'checkout': 0.06, 'currency': 0.8, 'email': 0.0, 'frontend': 0.04, 'image_provider': 0.0, 'payment': 0.0, 'product_catalog': 0.0, 'quote': 0.0, 'recommendation': 0.09, 'shipping': 0.0}

top-1: yes

top-3: yes