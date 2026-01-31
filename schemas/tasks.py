from typing import List, Optional
from pydantic import BaseModel, Field


class TaskSegment(BaseModel):
    index: int
    start_ts: int
    end_ts: int
    rtsp_url: str
    status: str = Field(default="pending")
    screenshot_path: Optional[str] = None
    error: Optional[str] = None


class TaskCreateRequest(BaseModel):
    date: str = Field(..., example="2025-11-03")
    base_rtsp: str = Field(
        default="rtsp://admin:admin123=@192.168.54.227:554",
        description="RTSP基础地址(不含路径)",
    )
    channel: str = Field(default="c2", description="通道名，如 c2")
    interval_minutes: int = Field(default=10, description="分段间隔，分钟")


class TaskCreateResponse(BaseModel):
    date: str
    total_segments: int
    segments: List[TaskSegment]
    # 新增字段：用于前端判断“任务是否已存在 / 部分新建”
    created_segments: int = Field(
        default=0,
        description="本次实际新建的任务分片数量",
    )
    existing_segments: int = Field(
        default=0,
        description="本次发现数据库中已存在的任务分片数量（未重复创建）",
    )
    message: Optional[str] = Field(
        default=None,
        description="提示消息（如任务已存在等）",
    )
    existing_count: Optional[int] = Field(
        default=None,
        description="已存在的任务数量",
    )
    created_count: Optional[int] = Field(
        default=None,
        description="本次创建的任务数量",
    )


class RunTaskRequest(BaseModel):
    date: str
    channel: str = "c2"
    base_rtsp: str = "rtsp://admin:admin123=@192.168.54.227:554"
    interval_minutes: int = 10
    screenshot_dir: str = "screenshots"
    crop_ocr_box: Optional[list[int]] = None  # [x1,y1,x2,y2]


class RunAllRequest(BaseModel):
    date: str
    interval_minutes: int = 10  # 用于不存在任务时生成任务的间隔


class RerunConfigRequest(BaseModel):
    date: str = Field(..., description="任务日期")
    rtsp_ip: Optional[str] = Field(None, description="RTSP IP地址")
    channel: Optional[str] = Field(None, description="通道")


class AutoScheduleRuleCreate(BaseModel):
    use_today: bool = Field(True, description="是否使用当天时间")
    custom_date: Optional[str] = Field(None, description="自定义日期（如果use_today=False）")
    base_rtsp: str = Field(..., description="RTSP基础地址")
    channel: str = Field(..., description="通道（c1-c4）")
    interval_minutes: int = Field(10, description="间隔分钟")
    trigger_time: str = Field(..., description="触发时间（HH:mm格式）")
    name: Optional[str] = Field(None, description="规则名称")


class AutoScheduleRuleUpdate(BaseModel):
    is_enabled: bool = Field(..., description="是否启用")

