## 1) Things We Added/Changed
- Removed temporary/stub functions in header
- Removed crafting raw UDP packets and checksum by hand (Performed by OS now.)
- Shifted responsibility of managing transport layer from receiver/sender.py into GameNetAPI, reliable.py + header.py + logger.py
- Sender and Receiver now use **GameNetAPI** over one UDP socket.
- Unified CSV logging via logger; add **exporter** for charts-latency.py
- Run scripts to start receiver/sender and capture logs

## 2) Things That Are Missing
- Reliable Transport semantics: reordering buffer, in-order delivery, skip-after-t, etc.
- For now, generate both text logs from sender.csv. RTT (needed for latency) is only recorded when ACKs are received, which happens on the sender side. receiver.csv doesn’t contain ACK-RX entries yet, so the exporter will write 0 lines if you use it for --mode receiver.

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

# 3) convert CSV logs to text logs for the chart script
python3 tools/export_for_charts.py logs/sender.csv   --mode sender
python3 tools/export_for_charts.py logs/receiver.csv --mode receiver
# Expect: logs/sender_log.txt and logs/receiver_log.txt

# 4) run chart script where the two text logs live
cd logs
python3 ../charts-latency.py
# Expect: PNG figures generated in logs/

## 4) Additional Notes

In theory, should be able to simulate delay/loss with tc-netem but it's not tested rigorously on my end.
