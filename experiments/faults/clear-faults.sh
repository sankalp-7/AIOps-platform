#!/usr/bin/env bash

kubectl delete virtualservice \
  -n otel-demo \
  -l aiops-fault=delay \
  --ignore-not-found
