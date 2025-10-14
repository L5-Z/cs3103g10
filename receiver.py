import argparse, socket, time, os
from hudp.api import GameNetAPI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--log", default="logs/session.csv")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.bind, args.port))

    api = GameNetAPI(sock, peer=None, log_path=args.log)

    def on_rel(b: bytes):
        # keep small and visible
        pass

    def on_unrel(b: bytes):
        pass

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