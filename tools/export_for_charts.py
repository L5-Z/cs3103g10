import argparse, csv, os, sys

# Convert GameNetAPI CSV logs into simple text logs for charts-latency.py.

CHAN_MAP = {"REL": 0, "UNREL": 1}

def default_out_path(csv_path: str, mode: str) -> str:
    base_dir = os.path.dirname(csv_path) or "."
    name = "sender_log.txt" if mode == "sender" else "receiver_log.txt"
    return os.path.join(base_dir, name)

def _get(row, *names, default=""):
    for n in names:
        if n in row and row[n] != "":
            return row[n]
    return default

def _maybe_sender_csv(csv_path: str) -> str:
    # If user passed receiver.csv but we need ACKs, fall back to sibling sender.csv
    base_dir = os.path.dirname(csv_path) or "."
    cand = os.path.join(base_dir, "sender.csv")
    return cand if os.path.exists(cand) else csv_path

def _emit_sender_lines(r, g) -> int:
    written = 0
    for row in r:
        dir_ = (_get(row, "dir").upper())
        ch   = _get(row, "channel", "chan")  # be tolerant
        seq  = _get(row, "seq")
        size = _get(row, "size")
        ts   = _get(row, "ts", "timestamp")
        if ch not in CHAN_MAP and ch != "ACK":
            continue
        if dir_ == "TX" and ch in CHAN_MAP:
            seq_val = seq if seq != "" else "0"
            g.write(f"SeqNo: {seq_val} ChannelType: {CHAN_MAP[ch]}\n")
            written += 1
        elif dir_ == "RX" and ch == "ACK":
            rtt = _get(row, "rtt_ms", "rtt")
            if seq and rtt:
                rtt_str = f"{rtt}ms" if not str(rtt).endswith("ms") else str(rtt)
                g.write(f"SeqNo: {seq} ChannelType: 0 RTT: {rtt_str}\n")
                written += 1
    return written

def _emit_receiver_lines(r, g) -> int:
    written = 0
    for row in r:
        dir_ = (_get(row, "dir").upper())
        ch   = _get(row, "channel", "chan")
        seq  = _get(row, "seq")
        ts   = _get(row, "ts", "timestamp")
        tss  = _get(row, "ts_send")
        size = _get(row, "size")
        act  = _get(row, "action", "event").lower()
        if dir_ == "RX" and ch in ("REL", "UNREL"):
            g.write(f"[RECV] {ch} seq={seq} ts_send={tss} ts={ts} size={size}\n")
            written += 1
        if dir_ == "RX" and ch == "REL" and act:
            g.write(f"[EV] {act.upper()} seq={seq}\n")  # deliver/buffer/dup/skip
            written += 1
    return written

def run(csv_path: str, out_path: str, mode: str) -> int:
    written = 0
    with open(csv_path, newline="") as f, open(out_path, "w") as g:
        r = csv.DictReader(f)
        if mode == "sender":
            written = _emit_sender_lines(r, g)
        else:
            # Primary: receiver-side RX lines + events (no RTT here)
            written = _emit_receiver_lines(r, g)
    # For receiver mode, if we didn’t get any RTT lines (expected), also try sender.csv to add ACK RTTs:
    if mode == "receiver":
        # Append ACK-derived RTTs from sender.csv if available
        sender_csv = _maybe_sender_csv(csv_path)
        try:
            with open(sender_csv, newline="") as f2, open(out_path, "a") as g2:
                r2 = csv.DictReader(f2)
                # Only append ACK lines
                for row in r2:
                    dir_ = (_get(row, "dir").upper())
                    ch   = _get(row, "channel", "chan")
                    if dir_ == "RX" and ch == "ACK":
                        seq = _get(row, "seq")
                        rtt = _get(row, "rtt_ms", "rtt")
                        if seq and rtt:
                            rtt_str = f"{rtt}ms" if not str(rtt).endswith("ms") else str(rtt)
                            g2.write(f"SeqNo: {seq} ChannelType: 0 RTT: {rtt_str}\n")
                            written += 1
        except FileNotFoundError:
            pass
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
