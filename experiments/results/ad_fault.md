Fault injected - 2s service delay on ad service using faults/inject-delay.sh

MicroRCA ranking:
 1. ad                        PPR=0.540541 AS=0.226501
 2. frontend                  PPR=0.459459 AS=0.000000
 3. otel-collector-agent      PPR=0.000000 AS=0.000000
 4. flagd                     PPR=0.000000 AS=0.000000

 top-1: yes

 top-3: yes




Jev ranking:
{'ad': 0.67, 'cart': 0.0, 'checkout': 0.0, 'currency': 0.0, 'email': 0.0, 'frontend': 0.18, 'image_provider': 0.0, 'payment': 0.0, 'product_catalog': 0.0, 'quote': 0.0, 'recommendation': 0.15, 'shipping': 0.0}

top-1: yes
top-3: yes
