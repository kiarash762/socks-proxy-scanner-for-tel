import socks
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

TELEGRAM_IP = "149.154.167.91"
TELEGRAM_PORT = 443
TIMEOUT = 5
THREADS = 90

def test_port(proxy_ip, port):
    try:
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, proxy_ip, port)
        s.settimeout(TIMEOUT)
        s.connect((TELEGRAM_IP, TELEGRAM_PORT))
        s.close()
        return port
    except:
        return None

def main():
    proxy_ip = input("enter IP: ").strip()
    if not proxy_ip:
        print("no valid IP.")
        return

    input_filename = f"fixed_{proxy_ip}.txt"
    output_filename = f"{proxy_ip}-works.txt"

    try:
        with open(input_filename, "r") as f:
            ports = [int(line.strip()) for line in f if line.strip().isdigit()]
    except FileNotFoundError:
        print(f" file {input_filename} not found. please make it in that folder")
        return

    if not ports:
        print(" no valid ports on the file .")
        return

    print(f"testing {len(ports)} port on {proxy_ip}...")
    working = []
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(test_port, proxy_ip, p): p for p in ports}
        for future in as_completed(futures):
            port = future.result()
            if port:
                working.append(port)
                print(f"[+] port {port} works")
            # print(f"[-] پورت {futures[future]} کار نکرد")

    print("\n--- final result ---")
    if working:
        print("working ports:")
        for p in working:
            print(f"{proxy_ip}:{p}")
        with open(output_filename, "w") as f:
            for p in working:
                f.write(f"{p}\n")
        print(f"\n the list of working ports saved on {output_filename}.")
    else:
        print("no working ports")

if __name__ == "__main__":
    main()