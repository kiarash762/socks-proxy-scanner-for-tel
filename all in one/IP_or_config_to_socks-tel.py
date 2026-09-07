import asyncio
import os
import platform
import re
import socks
import socket
import base64
import json
from concurrent.futures import ThreadPoolExecutor

# تنظیمات کنترل سرعت (Concurrency)
PING_SEMAPHORE = asyncio.Semaphore(200)  # تعداد پینگ‌های همزمان
NMAP_SEMAPHORE = asyncio.Semaphore(5)    # تعداد اسکن‌های همزمان Nmap

# تنظیمات تست پروکسی
TELEGRAM_IP = "149.154.167.91"
TELEGRAM_PORT = 443
TIMEOUT = 5
MAX_TEST_THREADS = 100  # تعداد تردهای همزمان برای تست پورت‌ها

# ==========================================
# مرحله ۱: پینگ آسنکرون آی‌پي‌ها
# ==========================================
async def ping_ip(ip):
    async with PING_SEMAPHORE:
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        timeout_val = '1000' if platform.system().lower() == 'windows' else '1'
        
        command = f"ping {param} 1 {timeout_param} {timeout_val} {ip}"
        proc = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        return ip if proc.returncode == 0 else None

# ==========================================
# مرحله ۲: اسکن پورت‌ها با Nmap و حل مشکل انکودینگ
# ==========================================
async def scan_ports(ip):
    async with NMAP_SEMAPHORE:
        print(f"[*] Scanning all ports for {ip}...")
        command = f"nmap -p- --open --min-rate 2000 -oG - {ip}"
        
        proc = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        
        encodings = ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1252', 'latin-1', 'cp1256']
        output = None
        
        for enc in encodings:
            try:
                output = stdout.decode(enc)
                break
            except UnicodeDecodeError:
                continue
                
        if output is None:
            output = stdout.decode('latin-1', errors='ignore')
        
        open_ports = []
        match = re.search(r"Ports:\s+(.*)", output)
        if match:
            ports_raw = match.group(1)
            for port_info in ports_raw.split(','):
                port_match = re.search(r"(\d+)/open", port_info)
                if port_match:
                    open_ports.append(int(port_match.group(1)))
                    
        if open_ports:
            print(f"[+] Found ports {open_ports} on IP: {ip}")
        return ip, open_ports

# ==========================================
# مرحله ۴: تابع تست پروکسی (ترد سیف و سینک)
# ==========================================
def test_socks_proxy_sync(proxy_ip, port):
    try:
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, proxy_ip, port)
        s.settimeout(TIMEOUT)
        s.connect((TELEGRAM_IP, TELEGRAM_PORT))
        s.close()
        print(f"[✓] Working Proxy Found! -> {proxy_ip}:{port}")
        return proxy_ip, port, True
    except:
        return proxy_ip, port, False

# ==========================================
# مدیریت و اجرای مراحل (Main Core)
# ==========================================
async def main():
    final_ips = set()
    
    # ------------------------------------------
    # بخش اول ورودی: خواندن از ip.txt
    # ------------------------------------------
    if os.path.exists("ip.txt"):
        print("[*] Reading from ip.txt...")
        with open("ip.txt", "r", encoding='utf-8', errors='ignore') as f:
            for line in f:
                ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line.strip())
                if ip_match:
                    final_ips.add(ip_match.group(1))

    # ------------------------------------------
    # بخش دوم ورودی: استخراج آی‌پی از config.txt (با پشتیبانی از VMess)
    # ------------------------------------------
    if os.path.exists("config.txt"):
        print("[*] Reading and extracting IPs from config.txt...")
        with open("config.txt", "r", encoding='utf-8', errors='ignore') as f:
            for line in f:
                cleaned_line = line.strip()
                if not cleaned_line:
                    continue
                
                # ۱. پردازش کانفیگ‌های vmess (Base64)
                if cleaned_line.startswith("vmess://"):
                    try:
                        b64_data = cleaned_line[8:]
                        # افزودن Padding جهت جلوگیری از خطای Base64
                        b64_data += '=' * (-len(b64_data) % 4)
                        decoded_json = base64.b64decode(b64_data).decode('utf-8', errors='ignore')
                        vmess_config = json.loads(decoded_json)
                        host = vmess_config.get("add", "")
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
                            final_ips.add(host)
                    except Exception:
                        pass
                    continue

                # ۲. سایر کانفیگ‌ها (vless, trojan, ss, etc.)
                if "server=" in cleaned_line:
                    server_match = re.search(r'server=([^&]+)', cleaned_line)
                    if server_match:
                        host = server_match.group(1)
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
                            final_ips.add(host)
                else:
                    at_match = re.search(r'@([^:/?#]+)', cleaned_line)
                    if at_match:
                        host = at_match.group(1)
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
                            final_ips.add(host)           
                    else:
                        ip_raw_match = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', cleaned_line)
                        for extracted_ip in ip_raw_match:
                            final_ips.add(extracted_ip)

    ips = list(final_ips)

    if not ips:
        print("Error: No valid IPv4 addresses found in ip.txt or config.txt")
        print("Done")
        return

    print(f"[!] Loaded and cleaned {len(ips)} unique IPs from all input sources.")

    # --- مرحله ۱ ---
    print(f"--- Stage 1: Pinging {len(ips)} IPs ---")
    ping_tasks = [ping_ip(ip) for ip in ips]
    ping_results = await asyncio.gather(*ping_tasks)
    active_ips = [ip for ip in ping_results if ip is not None]
    print(f">> Stage 1 Completed. Active IPs: {len(active_ips)}\n")

    if not active_ips:
        print("No active IPs found to scan.")
        print("Done")
        return

    # --- مرحله ۲ ---
    print(f"--- Stage 2: Scanning open ports with Nmap ---")
    scan_tasks = [scan_ports(ip) for ip in active_ips]
    scan_results = await asyncio.gather(*scan_tasks)
    print(">> Stage 2 Completed.\n")

    # --- مراحل ۳، ۴ و آخر ---
    print(f"--- Stage 3 & 4: Generating and Testing Proxies (Parallel Threading) ---")
    
    all_pairs_to_test = []
    for ip, ports in scan_results:
        for port in ports:
            all_pairs_to_test.append((ip, port))
            
    if not all_pairs_to_test:
        print("No open ports found to test.")
        print("Done")
        return

    print(f"[*] Total IP:Port pairs to test: {len(all_pairs_to_test)}. Testing with {MAX_TEST_THREADS} threads...")

    working_proxies_count = 0
    loop = asyncio.get_running_loop()
    
    with ThreadPoolExecutor(max_workers=MAX_TEST_THREADS) as executor:
        tasks = [
            loop.run_in_executor(executor, test_socks_proxy_sync, ip, port)
            for ip, port in all_pairs_to_test
        ]
        
        test_results = await asyncio.gather(*tasks)
        
        for ip, port, is_working in test_results:
            if is_working:
                working_proxies_count += 1
                tg_link = f"https://t.me/socks?server={ip}&port={port}"
                with open("Tel_socks.txt", "a", encoding='utf-8') as out_file:
                    out_file.write(tg_link + "\n")

    print(f"\n>> All Stages Finished!")
    print(f">> Total working proxies saved to 'Tel_socks.txt': {working_proxies_count}")
    print("Done")

if __name__ == "__main__":
    if platform.system().lower() == 'windows':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())