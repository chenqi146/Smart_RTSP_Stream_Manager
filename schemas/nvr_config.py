from typing import List, Optional
from pydantic import BaseModel, Field


class ParkingSpaceInfo(BaseModel):
    """车位信息"""
    space_id: str = Field(..., description="车位ID")
    space_name: str = Field(..., description="车位编号")
    bbox: List[int] = Field(..., description="车位坐标 [x, y, width, height]")


class ChannelConfigCreate(BaseModel):
    """通道配置创建请求"""
    channel_code: str = Field(..., description="通道编号（如 c1/c2/c3/c4）")
    camera_ip: Optional[str] = Field(None, description="摄像头IP地址")
    camera_name: Optional[str] = Field(None, description="摄像头名称")
    camera_sn: Optional[str] = Field(None, description="摄像头SN")
    track_space: Optional[str] = Field(None, description="识别停车区域坐标（track_space 原始值）")
    parking_spaces: Optional[List[ParkingSpaceInfo]] = Field(None, description="关联车位信息")


class ChannelConfigUpdate(BaseModel):
    """通道配置更新请求"""
    channel_code: Optional[str] = Field(None, description="通道编号")
    camera_ip: Optional[str] = Field(None, description="摄像头IP地址")
    camera_name: Optional[str] = Field(None, description="摄像头名称")
    camera_sn: Optional[str] = Field(None, description="摄像头SN")
    track_space: Optional[str] = Field(None, description="识别停车区域坐标（track_space 原始值）")
    parking_spaces: Optional[List[ParkingSpaceInfo]] = Field(None, description="关联车位信息")


class ChannelConfigResponse(BaseModel):
    """通道配置响应"""
    id: int
    nvr_config_id: int
    channel_code: str
    camera_ip: Optional[str]
    camera_name: Optional[str]
    camera_sn: Optional[str]
    track_space: Optional[str]
    parking_spaces: Optional[List[ParkingSpaceInfo]]
    created_at: Optional[str]
    updated_at: Optional[str]


class NvrConfigCreate(BaseModel):
    """NVR配置创建请求"""
    nvr_ip: str = Field(..., description="NVR IP地址")
    parking_name: str = Field(..., description="车场名称")
    nvr_username: str = Field(..., description="NVR账号")
    nvr_password: str = Field(..., description="NVR密码")
    nvr_port: int = Field(554, description="NVR端口")
    db_host: Optional[str] = Field(None, description="数据库地址")
    db_user: Optional[str] = Field(None, description="数据库账号")
    db_password: Optional[str] = Field(None, description="数据库密码")
    db_port: Optional[int] = Field(3306, description="数据库端口")
    db_name: Optional[str] = Field(None, description="数据库名称")
    channels: Optional[List[ChannelConfigCreate]] = Field(None, description="通道配置列表")


class NvrConfigUpdate(BaseModel):
    """NVR配置更新请求"""
    parking_name: Optional[str] = Field(None, description="车场名称")
    nvr_username: Optional[str] = Field(None, description="NVR账号")
    nvr_password: Optional[str] = Field(None, description="NVR密码")
    nvr_port: Optional[int] = Field(None, description="NVR端口")
    db_host: Optional[str] = Field(None, description="数据库地址")
    db_user: Optional[str] = Field(None, description="数据库账号")
    db_password: Optional[str] = Field(None, description="数据库密码")
    db_port: Optional[int] = Field(None, description="数据库端口")
    db_name: Optional[str] = Field(None, description="数据库名称")


class NvrConfigResponse(BaseModel):
    """NVR配置响应"""
    id: int
    nvr_ip: str
    parking_name: str
    nvr_username: str
    nvr_password: str
    nvr_port: int
    db_host: Optional[str]
    db_user: Optional[str]
    db_password: Optional[str]
    db_port: Optional[int]
    db_name: Optional[str]
    channels: List[ChannelConfigResponse]
    created_at: Optional[str]
    updated_at: Optional[str]


class ChannelView(BaseModel):
    """
    通道统一视图模型：
    用于前端在各个页面（参数设置 / 自动分配 / 任务列表 / 图片列表等）
    以统一结构获取通道信息。
    """
    id: int = Field(..., description="通道配置ID（channel_configs.id）")
    nvr_id: int = Field(..., description="所属NVR配置ID（nvr_configs.id）")
    nvr_ip: str = Field(..., description="NVR IP地址")
    parking_name: Optional[str] = Field(None, description="车场名称")
    base_rtsp: str = Field(..., description="RTSP基础地址（rtsp://user:pass@ip:port）")
    channel_code: str = Field(..., description="通道编号（如 c1/c2/c3/c4）")
    camera_ip: Optional[str] = Field(None, description="摄像头IP地址")
    camera_name: Optional[str] = Field(None, description="摄像头名称")
    camera_sn: Optional[str] = Field(None, description="摄像头SN")
