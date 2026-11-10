Fault injected - 2s service delay on recommendation service using faults/inject-delay.sh

MicroRCA Ranking:
 1. recommendation            PPR=0.540541 AS=0.328788
 2. frontend                  PPR=0.459459 AS=0.000000
 3. otel-collector-agent      PPR=0.000000 AS=0.000000
 4. product-catalog           PPR=0.000000 AS=0.000000
 5. flagd                     PPR=0.000000 AS=0.000000

top-3: yes

top-1: yes



Jev Ranking:
{'ad': 0.0, 'cart': 0.0, 'checkout': 0.01, 'currency': 0.0, 'email': 0.0, 'frontend': 0.13, 'image_provider': 0.0, 'payment': 0.01, 'product_catalog': 0.01, 'quote': 0.0, 'recommendation': 0.84, 'shipping': 0.0}

top-3: yes

top-1: yes