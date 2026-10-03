# AIOps Platform

A simple AIOps platform with an RCA engine built using a **System Dependency Graph (SDG)**.

<img width="982" height="635" alt="Screenshot 2026-10-03 at 3 44 50 PM" src="https://github.com/user-attachments/assets/2795c932-67dd-427b-b63d-608955f1267a" />

https://github.com/user-attachments/assets/82ea74f3-5c7f-4428-9262-025e58309c99

## Explanation

## Aim and Motivation of the Project

For any microservice-based application, the goal is to create an RCA engine that can deduce the root cause of a fault and suggest a possible fix.

Modern systems are becoming increasingly complex, with most companies moving toward microservice-based architectures. While this enables faster development and deployment, diagnosing and fixing these systems when they fail still remains a painful process.

There are several observability platforms that can alert engineers about which parts of an application are experiencing problems. However, reliably determining which specific service initiated the failure and why is still a difficult problem.

AIOps is one possible approach for addressing these operational challenges in complex distributed systems.

With the recent surge in AI development, AIOps has the potential to move beyond issue triaging and alert reduction toward broader capabilities such as automated **Root Cause Analysis (RCA)**.

This project focuses on identifying the root cause of a fault using system context and a **Service Dependency Graph (SDG)**.

---

## Workflow

### Step 1: Construct the SDG

The project uses Kiali to construct the [Service Dependency Graph](SDG/build_sdg_oteldemo.py) for the application.

The OpenTelemetry Demo application is used for this project and consists of approximately 20 microservices.

Running the above script generates the application's SDG in JSON format.

---

### Step 2: Inject Faults

Faults are injected into one of the services using the following script:

[inject-delay.sh](experiments/faults/inject-delay.sh)

---

### Step 3: Verify the Fault Through Prometheus

Verify that the injected fault is visible through Prometheus metrics.

Currently, the project primarily works with **latency faults**.

---

### Step 4: Detect Anomalies

Run the [collect_anomalies script](Prometheus/collect_anomalies_oteldemo.py) to detect anomalous services.

The detected anomalies are stored in JSON format.

---

### Step 5: Run the RCA Engine

The outputs from **Step 1** and **Step 4** are provided as inputs to the RCA engine.

The RCA engine currently uses two approaches to identify the leading root-cause candidates.

#### Method 1: PageRank Using Random Walk With Restart

This approach is inspired by the **MicroRCA** paper.

The RCA pipeline follows a topology-aware approach in which service dependencies are combined with runtime anomalies to narrow down likely fault origins.

The system first identifies anomalous services using signals such as latency, error rate, CPU, and memory, and maps these services onto the live Service Dependency Graph derived from Istio telemetry.

Instead of simply selecting the service with the largest anomaly, the RCA engine analyzes how failures could propagate through upstream and downstream dependencies.

It then ranks candidate root causes based on:

- Anomaly severity
- Position and relationships within the dependency graph

The highest-ranked candidates can then be enriched with logs, traces, Kubernetes events, and other operational information to provide additional evidence for the final diagnosis.

#### Method 2: JEV

Just JEV, nothing much
I genuinely feel this could be a much bigger breakthrough for the AIOps space than it first appears. LLMs have always been extremely good at looking at a pile of system context and reasoning about what probably went wrong. The problem is that you simply cannot keep throwing massive amounts of telemetry into a large LLM every few minutes in a production environment and hope everything works out nicely.

The input size alone becomes a problem — logs, metrics, traces, events, topology, and everything else add up very quickly, which means cost becomes a serious concern. Then there is speed. Traditional LLMs can take noticeably longer to reason through all that context, while RCA systems often need to run continuously and return answers quickly.

That is one of the reasons approaches such as **MicroRCA and other graph-based methods** make sense. They are fast, deterministic, relatively cheap, and can be executed frequently without burning through an API budget every time something looks slightly suspicious.

A small System one model like JEV potentially changes that trade-off. Instead of relying entirely on handcrafted graph algorithms simply because they are faster and cheaper than LLM reasoning, a model like JEV can potentially act as the fast reasoning layer itself — giving us model-based decision making without the latency and cost normally associated with large LLMs.

For context, while experimenting with JEV I used **187,731 tokens and the total cost was $0.0076**.


---

### Step 6: LLM-Based Explanation and Remediation

After the ranking is completed, information from the **top three root-cause candidates** is collected.

Additional contextual information can also be included, such as:

- Application logs
- Audit logs
- Metrics
- Traces
- Kubernetes events
- Service dependency information

This combined context is passed to an LLM to generate a more detailed explanation of the fault and suggest possible remediation steps.

---

## Demo

For a detailed demonstration, watch:

[Watch RCA Video](rca.mp4)
