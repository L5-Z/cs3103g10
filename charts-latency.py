"""
CS3103 Group 10 - Log Analysis Script
"""

# The script reads sender/receiver log files and plots latency, jitter and throughput.
# It’s okay if the receiver log is empty (RTT is only in sender logs for now).
# Requirements : matplotlib, pandas, numpy

import os
import sys
import csv
import argparse
import math
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PLOTS_DIR = "plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

def log(msg):
    print(msg, file=sys.stderr)

# helpers for reading the log files 
NUM_KEYS_LAT_MS = ("latency_ms", "rtt_ms", "one_way_ms")
TIME_KEYS_MS = ("recv_time_ms", "ack_time_ms", "timestamp_ms", "time_ms", "ts_ms", "time")
SEQ_KEYS = ("seq", "seqno", "sequence", "sequence_number")

def _to_float_safe(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None

def _try_read_csv_rows(path):
    for delim in (",", "\t", " "):
        try:
            with open(path, "r", newline="") as f:
                dr = csv.DictReader(f, delimiter=delim)
                rows = [r for r in dr]
                if rows and any(rows[0].keys()):
                    return rows
        except Exception:
            continue
    return None

def _try_read_kv_lines(path):
    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace("=", " ").replace(":", " ").split()
            d = {}
            for i in range(0, len(parts) - 1, 2):
                k, v = parts[i].lower(), parts[i + 1]
                d[k] = v
            if d:
                rows.append(d)
    return rows if rows else None

def load_text_log(path):
    if not path or not os.path.exists(path):
        return []
    rows = _try_read_csv_rows(path)
    if rows:
        return rows
    rows = _try_read_kv_lines(path)
    return rows or []

def first_present(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, "", "NA"):
            return k
    return None

def fix_timestamp_units(v):
    if v is None:
        return None
    try:
        v = float(v)
    except Exception:
        return None
    if v > 1e15:  
        return v / 1e6
    if v > 1e12:  
        return v
    if v > 1e9:  
        return v * 1000.0
    return v

def extract_series(rows):
    send_ts_by_seq = {}
    times_all = []

    for idx, r in enumerate(rows):
        t = fix_timestamp_units(r.get("ts_recv_ms"))
        if t is not None:
            times_all.append(t)

        ev  = (r.get("event") or "").lower()
        dir_ = (r.get("dir") or "").upper()
        ch  = (r.get("channel") or "").upper()

        s = r.get("seq")
        try:
            s = int(float(s)) if s not in (None, "", "NA") else None
        except Exception:
            s = None

        if ev == "send" and dir_ == "TX" and ch == "REL" and s is not None and t is not None:
            if s not in send_ts_by_seq:  
                send_ts_by_seq[s] = t

    seqs_lat, lat_vals = [], []
    missed = 0
    for r in rows:
        if (r.get("event") or "").lower() != "ack":
            continue

        s = r.get("seq")
        try:
            s = int(float(s)) if s not in (None, "", "NA") else None
        except Exception:
            s = None
        if s is None:
            continue

        t_ack  = fix_timestamp_units(r.get("ts_recv_ms"))
        t_send = send_ts_by_seq.get(s)

        if t_ack is None or t_send is None:
            missed += 1
            continue

        rtt = t_ack - t_send
        if 0 <= rtt <= 5000:  
            seqs_lat.append(s)
            lat_vals.append(rtt)
        else:
            missed += 1

    log(f"[info] matched ACKs with SENDs: {len(seqs_lat)} (missed {missed})")
    return {"seq_lat": seqs_lat, "lat": lat_vals, "time_all": times_all}

# plot helpers 
def save_line(y, x=None, title="", ylabel="", xlabel="", fname="plot.png"):
    if x is None:
        x = range(len(y))
    if not y:
        log(f"[skip] {fname}: no data")
        return
    try:
        plt.figure()
        plt.plot(x, y)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        out = os.path.join(PLOTS_DIR, fname)
        plt.tight_layout()
        plt.savefig(out, dpi=160)
        plt.close()
        log(f"[ok] saved {out}")
    except Exception as e:
        log(f"[err] {fname}: {e}")

def save_throughput(times_ms, window_s=1.0, fname="throughput.png"):
    t = [fix_timestamp_units(v) for v in times_ms if v is not None]
    t = [float(v) for v in t if v is not None and not math.isnan(v)]
    if len(t) < 2:
        log(f"[skip] {fname}: not enough timestamps")
        return
    t0 = min(t)
    t = [(v - t0) / 1000.0 for v in t]  
    tmax = max(t)
    bins = max(1, int(math.ceil(tmax / window_s)))
    counts = [0] * bins
    for v in t:
        idx = min(bins - 1, int(v // window_s))
        counts[idx] += 1
    centers = [(i + 0.5) * window_s for i in range(bins)]
    save_line(counts, centers,
              title="Throughput (pkts/s)",
              ylabel="pkts/s", xlabel="time (s)",
              fname=fname)

def jitter_rfc3550(lat_ms):
    if len(lat_ms) < 2:
        return []
    J_series = []
    J = 0.0
    prev = lat_ms[0]
    for i in range(1, len(lat_ms)):
        D = abs(lat_ms[i] - prev)
        J += (D - J) / 16.0
        J_series.append(J)
        prev = lat_ms[i]
    return J_series

def save_dual_line(y1, x1, y2, x2, label1, label2,
                   title="", ylabel="", xlabel="", fname="plot.png"):
    if not y1 and not y2:
        log(f"[skip] {fname}: no data"); return
    if x1 is None: x1 = range(len(y1))
    if x2 is None: x2 = range(len(y2))
    plt.figure()
    if y1: plt.plot(x1, y1, label=label1)
    if y2: plt.plot(x2, y2, label=label2)
    plt.title(title); plt.xlabel(xlabel); plt.ylabel(ylabel)
    plt.legend()
    out = os.path.join(PLOTS_DIR, fname)
    plt.tight_layout(); plt.savefig(out, dpi=160); plt.close()
    log(f"[ok] saved {out}")


def describe_stats(name, vals):
    if not vals:
        log(f"[stats] {name}: no samples")
        return
    import numpy as np
    a = np.array(vals, dtype=float)
    p95 = float(np.percentile(a, 95))
    msg = (f"[stats] {name}: count={len(a)}  mean={a.mean():.3f} ms  "
           f"median={np.median(a):.3f} ms  p95={p95:.3f} ms  max={a.max():.3f} ms")
    log(msg)

def main():
    ap = argparse.ArgumentParser(description="Latency/Jitter/Throughput charts (single or A vs B)")
    ap.add_argument("--sender", type=str, default=None, help="single run: sender CSV/TXT")
    ap.add_argument("--receiver", type=str, default="receiver.txt", help="(unused for RTT, optional)")
    ap.add_argument("--sender-a", type=str, help="first run: sender CSV/TXT")
    ap.add_argument("--sender-b", type=str, help="second run: sender CSV/TXT")
    ap.add_argument("--label-a", type=str, default="t=200ms")
    ap.add_argument("--label-b", type=str, default="dynamic t")
    args = ap.parse_args()

    compare_mode = bool(args.sender_a and args.sender_b)

    if compare_mode:
        rowsA = load_text_log(args.sender_a)
        rowsB = load_text_log(args.sender_b)
        if not rowsA and not rowsB:
            log("[err] No logs for A or B."); sys.exit(1)

        dataA = extract_series(rowsA)
        dataB = extract_series(rowsB)

        # latency
        save_dual_line(
            dataA["lat"], dataA["seq_lat"],
            dataB["lat"], dataB["seq_lat"],
            args.label_a, args.label_b,
            title="Latency per packet (A vs B)", ylabel="ms", xlabel="packet index",
            fname="latency_compare.png"
        )

        # jitter
        J_A = jitter_rfc3550(dataA["lat"])
        J_B = jitter_rfc3550(dataB["lat"])
        save_dual_line(
            J_A, None, J_B, None,
            args.label_a, args.label_b,
            title="Jitter (RFC3550) – A vs B", ylabel="ms", xlabel="packet index",
            fname="jitter_compare.png"
        )

        describe_stats(f"Latency {args.label_a}", dataA["lat"])
        describe_stats(f"Latency {args.label_b}", dataB["lat"])

        save_throughput(dataA["time_all"], fname="throughput_A.png")
        save_throughput(dataB["time_all"], fname="throughput_B.png")

        log("[done] compare charts saved in 'plots/'")
        return

    sender_path = args.sender or "sender.txt"
    sender_rows = load_text_log(sender_path)
    receiver_rows = load_text_log(args.receiver)

    if not sender_rows and not receiver_rows:
        log("[err] No logs found. Use --sender path."); sys.exit(1)
    if not sender_rows:
        log("[warn] sender log empty; using receiver (might have no RTT).")
    if not receiver_rows:
        log("[warn] receiver log empty; using sender only (normal for now).")

    base_rows = sender_rows if sender_rows else receiver_rows
    data = extract_series(base_rows)

    save_line(data["lat"], data["seq_lat"],
              title="Latency per packet", ylabel="ms", xlabel="packet index",
              fname="latency.png")
    J = jitter_rfc3550(data["lat"])
    save_line(J, title="Jitter (RFC3550 estimator)", ylabel="ms",
              xlabel="packet index", fname="jitter.png")
    save_throughput(data["time_all"], window_s=1.0, fname="throughput.png")
    log("[done] charts saved in 'plots/'")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"[err] crashed: {e}")
