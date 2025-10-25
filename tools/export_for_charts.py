'''
How to use:
python tools/export_for_charts.py logs/receiver.csv
This creates logs/receiver.csv.txt (feed that to charts-latency.py)
'''
import argparse, csv, sys, os

# Converts GameNetAPI CSV logs into simple text lines expected by charts-latency.py.
# We emit only RX/ACK lines with seq, send and recv times, and RTT if present.

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Input CSV from logger.py")
    ap.add_argument("-o", "--out", default=None, help="Output text file (default: <csv>.txt)")
    args = ap.parse_args()

    out_path = args.out or (args.csv + ".txt")
    total, written = 0, 0

    with open(args.csv, newline="") as f, open(out_path, "w") as g:
        r = csv.DictReader(f)
        for row in r:
            total += 1
            try:
                # Expected CSV columns from logger.py / GameNetAPI:
                # ts_recv_ms, dir, channel, seq, send_ts_ms, rtt_ms, retries, event, deadline_t_ms, len_bytes
                seq = row.get("seq")
                send_ts = row.get("send_ts_ms")
                recv_ts = row.get("ts_recv_ms")
                rtt = row.get("rtt_ms") or ""
                chan = row.get("channel")
                ev = row.get("event") or ""

                if not seq or not send_ts or not recv_ts:
                    continue

                # Simple line format; charts-latency.py parses "SeqNo:" and timestamps.
                # Keep fields conservative so existing regex still matches.
                line = f"SeqNo: {seq} Sent: {send_ts} Recv: {recv_ts}"
                if rtt:
                    line += f" RTT: {rtt}"
                if chan:
                    line += f" Chan: {chan}"
                if ev:
                    line += f" Ev: {ev}"
                g.write(line + "\n")
                written += 1
            except Exception:
                # Skip malformed lines quietly
                continue

    print(f"Wrote {written}/{total} lines to {out_path}")

if __name__ == "__main__":
    main()
