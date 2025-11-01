## 1) Things We Added/Changed
- Integrated **GameNetAPI** end-to-end (single UDP socket; REL/UNR/ACK demux).
- Implemented **reordering buffer + in-order delivery** in `ReliableReceiver`.
- Added transport event logging for reliable RX: `action=deliver|buffer|dup`.
- Unified CSV logging via `logger.Logger`; exporter to plain-text logs for charts.
- Run scripts to start receiver/sender and capture logs.

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
