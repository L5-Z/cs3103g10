import argparse, csv, os

# Convert GameNetAPI CSV logs into simple text logs for charts-latency.py.

''' How to use (From Project Root)
# From project root
python tools/export_for_charts.py logs/sender.csv   --mode sender
python tools/export_for_charts.py logs/receiver.csv --mode receiver
# charts-latency.py will now find sender_log.txt and receiver_log.txt by default
'''

CHAN_MAP = {"REL": 0, "UNREL": 1}

def default_out_path(csv_path: str, mode: str) -> str:
    base_dir = os.path.dirname(csv_path) or "."
    name = "sender_log.txt" if mode == "sender" else "receiver_log.txt"
    return os.path.join(base_dir, name)

def run(csv_path: str, out_path: str, mode: str) -> int:
    written = 0
    with open(csv_path, newline="") as f, open(out_path, "w") as g:
        r = csv.DictReader(f)
        for row in r:
            dir_ = (row.get("dir") or "").upper()
            ch = row.get("channel") or ""
            seq = row.get("seq") or ""
            rtt = row.get("rtt_ms") or ""

            # Map channel label -> 0/1
            if ch not in CHAN_MAP and ch != "ACK":
                continue
            if ch == "ACK":
                chan_val = 0  # ACK pertains to reliable
            else:
                chan_val = CHAN_MAP[ch]

            if mode == "sender":
                # Only TX rows for REL/UNREL; synthesize seq=0 when absent (UNREL).
                if dir_ != "TX" or ch not in CHAN_MAP:
                    continue
                seq_val = seq if seq != "" else "0"
                g.write(f"SeqNo: {seq_val} ChannelType: {chan_val}\n")
                written += 1

            elif mode == "receiver":
                # Use RX ACK rows to get RTT per seq on reliable channel.
                if dir_ != "RX" or ch != "ACK":
                    continue
                if seq == "" or rtt == "":
                    continue
                rtt_str = f"{rtt}ms" if not str(rtt).endswith("ms") else str(rtt)
                g.write(f"SeqNo: {seq} ChannelType: {chan_val} RTT: {rtt_str}\n")
                written += 1
    return written

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Input CSV path from logger.py")
    ap.add_argument("--mode", choices=["sender", "receiver"], required=True, help="Which text log to produce")
    ap.add_argument("-o", "--out", default=None, help="Output file (default: sender_log.txt/receiver_log.txt next to CSV)")
    args = ap.parse_args()

    out_path = args.out or default_out_path(args.csv, args.mode)
    written = run(args.csv, out_path, args.mode)
    print(f"Wrote {written} lines to {out_path}")

if __name__ == "__main__":
    main()
