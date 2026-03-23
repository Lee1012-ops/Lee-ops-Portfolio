import os
# 清除系统代理，让 AKshare / curl_cffi / requests 全部直连
# 必须在所有网络库 import 之前执行
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"]  = "*"

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from routers import stock


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时登录 Baostock
    from services.baostock_client import ensure_login
    try:
        ensure_login()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Baostock 启动登录失败（A股历史数据可能不可用）: %s", e)
    yield
    # 关闭时退出 Baostock
    from services.baostock_client import logout
    logout()


app = FastAPI(
    title="全球股票分析系统",
    description="支持A股、美股、港股的综合分析平台（数据源：Baostock + AKshare，无第三方依赖）",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(stock.router, prefix="/api", tags=["股票分析"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "全球股票分析系统运行正常"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
