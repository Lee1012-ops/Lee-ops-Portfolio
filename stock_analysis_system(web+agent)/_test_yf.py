"""测试三市场数据获取"""
import os
# 清除代理，保证直连
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"]  = "*"

import sys, time, logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
sys.path.insert(0, ".")

from services.baostock_client import ensure_login, logout
ensure_login()

def test(name, fn):
    t = time.time()
    try:
        result = fn()
        hist = result.get("history_df")
        price = result.get("realtime", {}).get("current_price")
        stock_name = result.get("stock_name", "").encode("gbk","replace").decode("gbk")
        print(f"  OK  {name}: name={stock_name}, price={price}, bars={len(hist)}, {round(time.time()-t,1)}s")
    except Exception as e:
        msg = str(e).encode("gbk","replace").decode("gbk")
        print(f"  FAIL {name}: {msg}")

from services.data_fetcher import fetch_a_stock, fetch_us_stock, fetch_hk_stock

print("\n=== A shares ===")
test("000001", lambda: fetch_a_stock("000001", 30))

print("\n=== US stocks ===")
test("AAPL",   lambda: fetch_us_stock("AAPL", 30))
test("NVDA",   lambda: fetch_us_stock("NVDA", 30))

print("\n=== HK stocks ===")
test("00700",  lambda: fetch_hk_stock("00700", 30))

logout()
print("\nDone")
