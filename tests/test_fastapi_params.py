"""
测试FastAPI参数传递 - 检查Query alias是否正确工作
"""
from fastapi import FastAPI, Query
from typing import Optional
import uvicorn

app = FastAPI()

@app.get("/test")
def test_params(
    channel_eq: Optional[str] = Query(None, alias="channel__eq"),
    channel: Optional[str] = None,
):
    """测试参数传递"""
    return {
        "channel_eq": channel_eq,
        "channel": channel,
        "channel_eq_type": type(channel_eq).__name__,
        "channel_eq_is_none": channel_eq is None,
    }

if __name__ == "__main__":
    print("启动测试服务器...")
    print("访问: http://localhost:8006/test?channel__eq=c2")
    print("访问: http://localhost:8006/test?channel_eq=c2")
    print("访问: http://localhost:8006/test?channel=c2")
    uvicorn.run(app, host="0.0.0.0", port=8006)

