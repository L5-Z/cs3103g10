import argparse, socket, time, random
from utilities import make_mock_game_data
from gamenetapi import GameNetAPI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="Receiver host")
    ap.add_argument("--port", type=int, required=True, help="Receiver port")
    ap.add_argument("--duration", type=int, default=3000, help="Seconds to run")
    ap.add_argument("--pps", type=int, default=40, help="Packets per second total")
    ap.add_argument("--reliable-ratio", type=float, default=0.5, help="Fraction sent on reliable channel")
    ap.add_argument("--log", default="logs/sender.csv", help="Sender-side transport log")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    api = GameNetAPI(sock, log_path=args.log)
    api.set_peer((args.host, args.port))

    def on_ack(seq: int, rtt_ms: int):
        pass 

    api.set_callbacks(reliable_cb=None, unreliable_cb=None, ack_cb=on_ack)
    api.start()

    interval = 1.0 / max(1, args.pps)
    end_time = time.time() + args.duration
    i = 0

    try:
        next_send = time.time()
        while time.time() < end_time:
            reliable = (random.random() < args.reliable_ratio)
            payload = make_mock_game_data(i)
            api.send(payload, reliable=reliable, urgency_ms=0)
            i += 1

            next_send += interval
            sleep_for = next_send - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_send = time.time()  
    finally:
        api.stop()

if __name__ == "__main__":
    main()
