import argparse, socket, time, os, json, random
from hudp.api import GameNetAPI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="Receiver host")
    ap.add_argument("--port", type=int, required=True, help="Receiver port")
    ap.add_argument("--duration", type=int, default=30, help="Seconds to run")
    ap.add_argument("--pps", type=int, default=40, help="Packets per second total")
    ap.add_argument("--reliable-ratio", type=float, default=0.5, help="Fraction sent on reliable channel")
    ap.add_argument("--log", default="logs/session.csv", help="Receiver will write logs; sender logs a few TX events")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    peer = (args.host, args.port)
    api = GameNetAPI(sock, peer, log_path=args.log)
    api.start()

    def mk_payload(i):
        # simple JSON-like payload (independent packets)
        obj = {"i": i, "ts": int(time.time()*1000), "x": random.random(), "y": random.random()}
        return json.dumps(obj).encode("utf-8")

    total = args.duration * args.pps
    interval = 1.0 / max(1, args.pps)
    i = 0
    start = time.time()
    try:
        while i < total and (time.time() - start) < args.duration + 1:
            reliable = (random.random() < args.reliable_ratio)
            urgency_ms = 40 if reliable and (random.random() < 0.2) else 0  # 20% marked a bit urgent
            api.send(mk_payload(i), reliable=reliable, urgency_ms=urgency_ms)
            i += 1
            time.sleep(interval)
    finally:
        api.stop()

if __name__ == "__main__":
    main()