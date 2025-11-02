import argparse, socket, time, json
from gamenetapi import GameNetAPI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--log", default="logs/receiver.csv")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--peer-host", default=None)
    ap.add_argument("--peer-port", type=int, default=None)
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.bind, args.port))

    api = GameNetAPI(sock, log_path=args.log, verbose=args.verbose)
    if args.peer_host and args.peer_port:
        api.set_peer((args.peer_host, args.peer_port))

    def on_rel(b: bytes):
        # app-layer handling for reliable messages
        try:
            obj = json.loads(b.decode("utf-8"))
            print(f"[REL] i={obj.get('i')} ts={obj.get('ts')} x={obj.get('x'):.3f} y={obj.get('y'):.3f}")
        except Exception:
            print(f"[REL] {len(b)} bytes")

    def on_unrel(b: bytes):
        # app-layer handling for unreliable messages
        try:
            obj = json.loads(b.decode("utf-8"))
            print(f"[UNR] i={obj.get('i')} ts={obj.get('ts')} x={obj.get('x'):.3f} y={obj.get('y'):.3f}")
        except Exception:
            print(f"[UNR] {len(b)} bytes")

    api.set_callbacks(on_rel, on_unrel)
    api.start()
    print(f"Receiver listening on {args.bind}:{args.port}. Logs -> {args.log}")

    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        api.stop()

if __name__ == "__main__":
    main()

