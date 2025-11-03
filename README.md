## 1) Things We Added/Changed
- Removed temporary/stub functions in header
- Removed crafting raw UDP packets and checksum by hand (Performed by OS now.) 
- Shifted responsibility of managing transport layer from receiver/sender.py into GameNetAPI, reliable.py + header.py + logger.py
- Sender and Receiver now use **GameNetAPI** over one UDP socket.
- Unified CSV logging via logger; add **exporter** for charts-latency.py
- Run scripts to start receiver/sender and capture logs

## 2) Things That Are Missing
- Reliable Transport semantics: reordering buffer, in-order delivery, skip-after-t, etc. (Retransmission time (t = 200ms part of the assignment))
- For now, generate both text logs from sender.csv. RTT (needed for latency) is only recorded when ACKs are received, which happens on the sender side. receiver.csv doesn’t contain ACK-RX entries yet, so the exporter will write 0 lines if you use it for --mode receiver.

## 3) How To Test (Quickstart) & Expected Behavior

# 1) start receiver (terminal A)
chmod +x scripts/run_receiver.sh scripts/run_sender.sh
./scripts/run_receiver.sh

# 2) start sender (terminal B)
./scripts/run_sender.sh

(For Verbose Option)
./scripts/run_sender.sh --verbose --print-every 10

# 3) convert CSV logs to text logs for the chart script
python3 tools/export_for_charts.py logs/sender.csv   --mode sender

python3 tools/export_for_charts.py logs/receiver.csv --mode receiver

# 4) run chart script where the two text logs live
cd logs
python3 ../charts-latency.py

## 4) Additional Notes

In theory, should be able to simulate delay/loss with tc-netem but it's not tested rigorously on my end.

## 5) Generate Charts (Single Run)

After logs are generated (sender.csv and receiver.csv), run:

cd logs
python3 ../charts-latency.py --sender sender.csv

Output files will be created inside logs/plots/:
- latency.png
- jitter.png
- throughput.png

## 6) Compare Two Runs (t = 200ms vs dynamic t)

To compare latency/jitter/throughput between two versions:

    a) Run with fixed t = 200ms
    ./scripts/run_receiver.sh     # (Terminal A)
    ./scripts/run_sender.sh       # (Terminal B)
    mv logs/sender.csv logs/sender_static.csv

    b) Run with dynamic t implementation
    ./scripts/run_sender.sh
    mv logs/sender.csv logs/sender_dynamic.csv

    c) Generate comparison charts
    cd logs
    python3 ../charts-latency.py \
    --sender-a sender_static.csv --label-a "t=200ms" \
    --sender-b sender_dynamic.csv --label-b "dynamic t"

This will create in logs/plots/:
- latency_compare.png  
- jitter_compare.png  
- throughput_A.png  
- throughput_B.png