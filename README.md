## 1) Things We Added/Changed
- Integrated **GameNetAPI** end-to-end (single UDP socket; REL/UNR/ACK demux).
- Implemented **reordering buffer + in-order delivery** in `ReliableReceiver`.
- Added transport event logging for reliable RX: `action=deliver|buffer|dup`.
- Unified CSV logging via `logger.Logger`; exporter to plain-text logs for charts.
- Run scripts to start receiver/sender and capture logs.
- `ts`, logged by the receiver represents milliseconds since epoch, masked to 32 bits. 

## 2) Things That Are Missing (for the team)
- **skip-after-t (gap timer)** in `ReliableReceiver` to bound waiting on a missing seq.
  - Target: t ≈ 200 ms (per assignment); emit `action=skip` when skipping.
- (Optional) Enrich charts to visualize `buffer/dup/skip` over time.

## 3) How To Test (Quickstart) & Expected Behavior

# 1) start receiver (terminal A)
chmod +x scripts/run_receiver.sh scripts/run_sender.sh
./scripts/run_receiver.sh
# Expect: console prints for REL/UNR deliveries; logs/receiver.csv grows

# 2) start sender (terminal B)
./scripts/run_sender.sh
# Optional verbose:
./scripts/run_sender.sh --verbose --print-every 10
# Expect: periodic [SEND] lines and [ACK] seq=… rtt=…ms; logs/sender.csv grows

# 3) convert CSV -> text logs for the chart script
python3 tools/export_for_charts.py logs/sender.csv   --mode sender
python3 tools/export_for_charts.py logs/receiver.csv --mode receiver
# Expect: logs/sender_log.txt, logs/receiver_log.txt and a short summary

# 4) run chart script where the two text logs live
cd logs
python3 ../charts-latency.py
# Expect: PNG figures in logs/ (performance_metrics.png, throughput_chart.png)

## 4) CSV Event Legend (reliable RX)
We add a small `action` field for reliable receive path:
- `deliver` – in-order delivery (including during buffer drain)
- `buffer`  – packet arrived ahead of a gap and was buffered
- `dup`     – duplicate/old packet dropped
- `skip`    – (to be added by teammate) head-of-line gap timed out and was skipped

These appear in CSV as rows like:
`[ts, "RX", "REL", seq, ts_send, rtt_ms, "", action, "", size]`.

## 5) tc-netem (optional, quick sanity)
Simulate reordering/delay to exercise the buffer:
- `sudo tc qdisc add dev <IF> root netem delay 40ms 5ms reorder 25% 50%`
- `sudo tc qdisc del dev <IF> root`

With reorder on, you should see `action=buffer` rows and later matching `action=deliver` when the missing seq arrives.


## 5) Testing Locally (Loopback)
# 0) Identify the interface used for your test
ip route get 127.0.0.1
# Expected: ... dev lo ...
# (If you’re testing across two machines, replace 127.0.0.1 with the peer IP
#  on *each* host to discover the correct dev, e.g. eth0/enp3s0/wlan0.)

# 00) Start fresh (avoid "File exists" errors if a qdisc was already present)
sudo tc qdisc del dev lo root 2>/dev/null || true

# 1) Add impairment with tc-netem (choose ONE of the variants below)

# 1a) Delay + jitter + reordering (good for buffer/reorder tests)
sudo tc qdisc add dev lo root netem delay 40ms 5ms reorder 25% 50%

# 1b) Delay + jitter only (no reordering)
sudo tc qdisc add dev lo root netem delay 40ms 5ms

# 1c) Delay + jitter + small random loss (see retransmissions)
sudo tc qdisc add dev lo root netem delay 40ms 5ms loss 1%

# 1d) Delay + jitter + rate limit (shape throughput; helps amplify reordering)
sudo tc qdisc add dev lo root netem delay 40ms 5ms rate 5mbit

# 1e) Combine (delay + jitter + reordering + small loss + rate limit)
sudo tc qdisc add dev lo root netem delay 40ms 5ms reorder 25% 50% loss 0.5% rate 5mbit

# 1f) Others
sudo tc qdisc add dev lo root netem delay 40ms 5ms reorder 35% 100%
sudo tc qdisc add dev lo root netem delay 40ms 5ms reorder 60% 100%

# misc (aggressive configurations to make re-ordering/dupes obvious)
# strong one-way delay + jitter + high reorder chance
sudo tc qdisc add dev lo root netem delay 60ms 20ms distribution normal reorder 80% 100% duplicate 3% loss 1%

# 2) Verify current qdisc
tc qdisc show dev lo
# Should display your chosen netem settings (e.g., delay 40.0ms 5.0ms reorder 25% 50%)

# 3) Run your apps (receiver first)
./scripts/run_receiver.sh --verbose
./scripts/run_sender.sh --verbose --print-every 10

# Alternatives
./scripts/run_sender.sh  --reliable-only --pps 300 --duration 10 --verbose --print-every 1

# 4) Export logs and generate charts
python3 tools/export_for_charts.py logs/sender.csv   --mode sender
python3 tools/export_for_charts.py logs/receiver.csv --mode receiver
python3 charts-latency.py --sender ./logs/receiver.csv
python3 charts-latency.py --receiver ./logs/receiver.csv

# 5) Clean up (remove impairment)
sudo tc qdisc del dev lo root

