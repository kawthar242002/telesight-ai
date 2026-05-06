"""
Dataset 1: 5G Network KPI Dataset
Simulates real-world 5G network KPIs per cell over time.
Columns: timestamp, cell_id, cell_type, throughput_mbps, latency_ms,
         packet_loss_pct, handover_count, rsrp_dbm, rsrq_db,
         prb_utilization_pct, active_users, slice_type, sla_compliant
"""
import pandas as pd
import numpy as np

np.random.seed(42)

N = 5000  # rows
timestamps = pd.date_range("2024-01-01", periods=N, freq="1min")
cell_ids = [f"CELL_{i:03d}" for i in np.random.randint(1, 21, N)]
cell_types = np.random.choice(["macro", "micro", "pico"], N, p=[0.5, 0.3, 0.2])
slice_types = np.random.choice(["eMBB", "URLLC", "mMTC", "HC"], N, p=[0.4, 0.3, 0.2, 0.1])

# Generate KPIs with slice-type-dependent distributions
throughput, latency, pkt_loss, ho_count = [], [], [], []
rsrp, rsrq, prb_util, active_users = [], [], [], []

for st in slice_types:
    if st == "eMBB":
        throughput.append(np.random.normal(820, 120))
        latency.append(np.random.normal(8.5, 2.1))
        pkt_loss.append(np.random.exponential(0.5))
        active_users.append(int(np.random.poisson(45)))
        prb_util.append(np.random.normal(72, 12))
    elif st == "URLLC":
        throughput.append(np.random.normal(250, 60))
        latency.append(np.random.normal(1.8, 0.4))
        pkt_loss.append(np.random.exponential(0.05))
        active_users.append(int(np.random.poisson(12)))
        prb_util.append(np.random.normal(55, 8))
    elif st == "mMTC":
        throughput.append(np.random.normal(45, 15))
        latency.append(np.random.normal(25, 8))
        pkt_loss.append(np.random.exponential(1.2))
        active_users.append(int(np.random.poisson(200)))
        prb_util.append(np.random.normal(35, 10))
    else:  # HC
        throughput.append(np.random.normal(1200, 200))
        latency.append(np.random.normal(4.5, 1.0))
        pkt_loss.append(np.random.exponential(0.2))
        active_users.append(int(np.random.poisson(8)))
        prb_util.append(np.random.normal(80, 10))

    ho_count.append(int(np.random.poisson(3)))
    rsrp.append(np.random.uniform(-120, -70))
    rsrq.append(np.random.uniform(-20, -3))

throughput = np.clip(throughput, 5, 2000).round(2)
latency = np.clip(latency, 0.3, 100).round(3)
pkt_loss = np.clip(pkt_loss, 0, 10).round(4)
prb_util = np.clip(prb_util, 5, 100).round(1)
rsrp = np.array(rsrp).round(1)
rsrq = np.array(rsrq).round(2)

# SLA compliance logic
sla = []
for i, st in enumerate(slice_types):
    if st == "eMBB":
        ok = throughput[i] >= 300 and latency[i] <= 20 and pkt_loss[i] <= 2.0
    elif st == "URLLC":
        ok = throughput[i] >= 100 and latency[i] <= 3.0 and pkt_loss[i] <= 0.1
    elif st == "mMTC":
        ok = latency[i] <= 50 and pkt_loss[i] <= 5.0
    else:
        ok = throughput[i] >= 500 and latency[i] <= 10 and pkt_loss[i] <= 0.5
    sla.append(int(ok))

df = pd.DataFrame({
    "timestamp": timestamps,
    "cell_id": cell_ids,
    "cell_type": cell_types,
    "slice_type": slice_types,
    "throughput_mbps": throughput,
    "latency_ms": latency,
    "packet_loss_pct": pkt_loss,
    "handover_count": ho_count,
    "rsrp_dbm": rsrp,
    "rsrq_db": rsrq,
    "prb_utilization_pct": prb_util,
    "active_users": active_users,
    "sla_compliant": sla
})

df.to_csv("/home/claude/datasets/dataset1_5g_network_kpi.csv", index=False)
print(f"Dataset 1 saved: {df.shape[0]} rows x {df.shape[1]} cols")
print(df.head(3).to_string())
print("\nSLA compliance by slice:")
print(df.groupby("slice_type")["sla_compliant"].mean().round(3))
