#!/usr/bin/env python3
"""RuView CSI-node UDP receiver.

Listens for packets sent by the ESP32 firmware and pretty-prints vitals.
  Vitals  magic 0xC5110002 (1 Hz)  -> presence / breathing / heart-rate / persons
  CSI     magic 0xC5110001 (~20Hz) -> raw I/Q frames (counted only)

Usage: python3 udp_receiver.py [--port 5005] [--seconds N] [--raw]
"""
import socket, struct, argparse, time, sys

VITALS_MAGIC = 0xC5110002
CSI_MAGIC    = 0xC5110001
FEATURE_MAGIC= 0xC5110003
FUSED_MAGIC  = 0xC5110004

# packed: uint32 magic, u8 node_id, u8 flags, u16 breathing(*100),
# u32 heartrate(*10000), int8 rssi, u8 n_persons, 2x reserved,
# f motion, f presence, u32 timestamp_ms, u32 reserved2
VITALS_FMT = "<IBBHIbB2xffII"
VITALS_LEN = struct.calcsize(VITALS_FMT)  # 32

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--seconds", type=int, default=0, help="0 = run forever")
    ap.add_argument("--raw", action="store_true", help="hexdump unknown packets")
    a = ap.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", a.port))
    s.settimeout(1.0)
    print(f"Listening on udp/{a.port}  (Ctrl-C to stop)\n", flush=True)

    counts = {"vitals": 0, "csi": 0, "feature": 0, "fused": 0, "other": 0}
    end = time.time() + a.seconds if a.seconds else None
    last_summary = time.time()
    try:
        while True:
            if end and time.time() > end:
                break
            try:
                data, addr = s.recvfrom(4096)
            except socket.timeout:
                continue
            if len(data) < 4:
                continue
            magic = struct.unpack_from("<I", data, 0)[0]
            if magic == VITALS_MAGIC and len(data) >= VITALS_LEN:
                (_, node, flags, br, hr, rssi, npers, motion, pres, ts, _) = \
                    struct.unpack_from(VITALS_FMT, data, 0)
                presence = "YES" if flags & 1 else "no "
                fall     = "FALL!" if flags & 2 else "-"
                counts["vitals"] += 1
                print(f"[{addr[0]} n{node}] presence={presence} "
                      f"breath={br/100:5.1f}bpm  heart={hr/10000:6.1f}bpm  "
                      f"persons={npers}  rssi={rssi}dBm  motion={motion:7.2f}  "
                      f"score={pres:7.2f}  fall={fall}  t={ts}ms", flush=True)
            elif magic == CSI_MAGIC:
                counts["csi"] += 1
            elif magic == FEATURE_MAGIC:
                counts["feature"] += 1
            elif magic == FUSED_MAGIC:
                counts["fused"] += 1
            else:
                counts["other"] += 1
                if a.raw:
                    print(f"? {addr} {len(data)}B {data[:16].hex()}", flush=True)
            if time.time() - last_summary >= 5:
                print(f"   -- totals: vitals={counts['vitals']} csi={counts['csi']} "
                      f"feature={counts['feature']} fused={counts['fused']} "
                      f"other={counts['other']}", flush=True)
                last_summary = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\nDone. totals: {counts}")
        s.close()

if __name__ == "__main__":
    main()
