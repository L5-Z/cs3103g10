# Adaptive Hybrid Transport Protocol — Mini Project

CS3103 Assignment 4 mini-project: hybrid reliable/unreliable transport over UDP/QUIC, with measurements for latency, jitter, throughput, and delivery ratio.

---

## 1. Things That Are Missing (To-Do)

- *(Optional)* Enrich charts/logs to visualize over time:
  - `buffer` (buffer occupancy)
  - `dup` (duplicate packets)
  - `skip` (gap skips)

---

## 2. Apply Network Impairment (tc netem on Loopback)

All examples below assume you are impairing the **loopback** device (`lo`).

> **Recommended workflow:**  
> 1. Apply one `tc netem` configuration (this section).  
> 2. Run receiver & sender under that impairment (Section 3).  
> 3. Generate charts from the resulting logs (Section 4).  
> 4. Remove the impairment (cleanup at the end of this section).

### 2.1 Identify Loopback Device

```bash
# Check which device handles 127.0.0.1 (should be 'lo' for loopback)
ip route get 127.0.0.1
# Expected output: ... dev lo ...
```

### 2.2 Reset Any Existing qdisc on Loopback

Safe to run multiple times:

```bash
sudo tc qdisc del dev lo root 2>/dev/null || true
```

Check what is currently applied:

```bash
tc qdisc show dev lo
```

### 2.3 Delay Only (Extreme Fixed Delay)

Large one-way delay, no jitter or loss:

```bash
sudo tc qdisc add dev lo root netem delay 80ms
```

---

### 2.4 Jitter Only (Extreme Variation, Low Mean)

Netem models jitter as variation around a base delay. Setting base to 0 gives “pure jitter”:

```bash
sudo tc qdisc add dev lo root netem delay 0ms 25ms distribution normal
```

---

### 2.5 Loss Only (Extreme Loss to Stress Reliability)

High loss with correlation to create bursts:

```bash
sudo tc qdisc add dev lo root netem loss 10% 50%
```

- `10%` average loss  
- `50%` correlation → bursty loss

---

### 2.6 Reordering Only (Extreme Reordering, Minimal Delay)

Reordering works best with a small base delay:

```bash
sudo tc qdisc add dev lo root netem \
  delay 2ms \
  reorder 80% 100% gap 1
```

- Very high chance of out-of-order delivery  
- `gap 1` lets almost every packet be a reorder candidate

---

### 2.7 Combine All (Extreme “Chaos” Scenario)

Delay + jitter + high reordering + duplicates + mild loss + rate limiting:

```bash
sudo tc qdisc add dev lo root netem \
  delay 60ms 20ms distribution normal \
  reorder 80% 100% gap 1 \
  duplicate 3% \
  loss 1% 25% \
  rate 5mbit
```

This is a worst-case style configuration to stress the reliable channel.

---

### 2.8 Additional (Milder) Presets

**Delay + jitter + reordering (buffer/reorder tests):**

```bash
sudo tc qdisc add dev lo root netem delay 40ms 5ms reorder 25% 50%
```

**Delay + jitter only (no reordering):**

```bash
sudo tc qdisc add dev lo root netem delay 40ms 5ms
```

**Delay + jitter + small loss (observe retransmissions):**

```bash
sudo tc qdisc add dev lo root netem delay 40ms 5ms loss 1%
```

**Delay + jitter + rate limit (amplify queuing under load):**

```bash
sudo tc qdisc add dev lo root netem delay 40ms 5ms rate 5mbit
```

---

### 2.9 Cleanup (Remove Impairment After You’re Done)

After you have run experiments and generated charts (Sections 3 and 4), remove the impairment:

```bash
sudo tc qdisc del dev lo root
```

---

## 3. Run Receiver and Sender (Under Current tc netem)

With your chosen `tc netem` configuration already applied (Section 2), use two terminals:

### 3.1 Start Receiver

```bash
# Terminal A: Receiver
./scripts/run_receiver.sh --verbose
```

### 3.2 Start Sender

```bash
# Terminal B: Sender
./scripts/run_sender.sh --verbose --print-every 10
```

Alternative sender configuration (heavier reliable stream):

```bash
./scripts/run_sender.sh --reliable-only --pps 300 --duration 10 --verbose --print-every 1
```

Logs will be written to:

- `logs/sender.csv`
- `logs/receiver.csv`

### 3.3 Alternative

Alternatively, use the provided static and dynamic script (On one terminal)
```bash
### Option A — Dynamic timer (adaptive, default)
./scripts/run_dynamic.sh --verbose --duration 8 --pps 20 --reliable-ratio 0.7
```

```bash
### Option B — Static Timer
+./scripts/run_static.sh --verbose --t-static-ms 200 --duration 8 --pps 20 --reliable-ratio 0.7
```


Provided are some more settings to play around
```
# Terminal A (receiver):
./scripts/run_receiver.sh --verbose --t-mode dynamic

# Terminal B (sender):
./scripts/run_sender.sh --verbose --t-mode dynamic --duration 8 --pps 20 --reliable-ratio 0.7

# Heavier reliable stream (all REL):
./scripts/run_sender.sh --verbose --t-mode dynamic --duration 10 --pps 300 --reliable-ratio 1.0
```

---

## 4. Generating Charts From Logs

After running sender and receiver under the chosen impairment:

```bash
cd logs
python3 ../charts-latency.py --sender sender.csv
```

The script will create plots in `logs/plots/`:

- `latency.png`
- `jitter.png`
- `throughput.png`

You can repeat Sections 2–4 with different `tc netem` presets to build multiple datasets and compare behaviours.

---

## 5. Comparing Fixed t = 200 ms vs Dynamic t

### 5.1 Run with Fixed t = 200 ms

Configure `ReliableReceiver` to use a fixed gap timer of `t = 200 ms`, then (with your chosen netem config applied):

```bash
# Terminal A
./scripts/run_receiver.sh

# Terminal B
./scripts/run_sender.sh
```

Save the sender log:

```bash
mv logs/sender.csv logs/sender_static.csv
```

### 5.2 Run with Dynamic t

Rebuild or reconfigure `ReliableReceiver` to use the **dynamic** gap timer logic, then repeat the same experiment:

```bash
# Terminal A
./scripts/run_receiver.sh

# Terminal B
./scripts/run_sender.sh
```

Save the new sender log:

```bash
mv logs/sender.csv logs/sender_dynamic.csv
```

### 5.3 Generate Comparison Charts

```bash
cd logs
python3 ../charts-latency.py \
  --sender-a sender_static.csv --label-a "t=200ms" \
  --sender-b sender_dynamic.csv --label-b "dynamic t"
```

This will create (under `logs/plots/`):

- `latency_compare.png`
- `jitter_compare.png`
- `throughput_A.png`   (for `t = 200 ms`)
- `throughput_B.png`   (for `dynamic t`)
