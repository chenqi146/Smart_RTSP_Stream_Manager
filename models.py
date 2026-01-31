from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey, Float, JSON, Text, Index
from sqlalchemy.orm import relationship

from db import Base


class TaskBatch(Base):
    """任务批次表：对应前端“任务列表”，一条记录代表某天某IP某通道某时间段的一批截图任务"""

    __tablename__ = "task_batches"
    __table_args__ = {"comment": "任务批次表：某天某IP某通道某时间段的一批截图任务"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主任务ID（任务批次）",
    )
    date = Column(
        String(10),
        index=True,
        nullable=False,
        comment="任务所属日期，格式：YYYY-MM-DD",
    )
    ip = Column(
        String(64),
        index=True,
        nullable=True,
        comment="摄像头IP",
    )
    channel = Column(
        String(16),
        index=True,
        nullable=True,
        comment="通道编号（如 c1/c2/c3/c4）",
    )
    base_rtsp = Column(
        String(512),
        nullable=False,
        comment="RTSP基础地址（不含时间段部分）",
    )
    start_ts = Column(
        BigInteger,
        nullable=False,
        comment="这批任务整体的起始时间戳（秒）",
    )
    end_ts = Column(
        BigInteger,
        nullable=False,
        comment="这批任务整体的结束时间戳（秒）",
    )
    interval_minutes = Column(
        Integer,
        nullable=False,
        comment="截图间隔分钟数",
    )
    status = Column(
        String(32),
        default="pending",
        comment="整批任务状态：pending/running/completed/failed/partial_failed",
    )
    task_count = Column(
        Integer,
        default=0,
        comment="子任务数量（tasks 条数）",
    )
    created_from_rule_id = Column(
        Integer,
        ForeignKey("auto_schedule_rules.id"),
        nullable=True,
        comment="来源的自动排程规则ID（外键：auto_schedule_rules.id）",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录最近更新时间（UTC）",
    )

    tasks = relationship("Task", back_populates="batch")


class Task(Base):
    """截图任务明细表：一条记录代表某个日期、某个时间段、某个通道上的一次截图任务"""

    __tablename__ = "tasks"
    __table_args__ = {"comment": "截图任务明细表：某天某时间段某通道的一次截图任务"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    batch_id = Column(
        Integer,
        ForeignKey("task_batches.id"),
        nullable=True,
        comment="所属任务批次ID（外键：task_batches.id）",
    )
    date = Column(
        String(10),
        index=True,
        nullable=False,
        comment="任务所属日期，格式：YYYY-MM-DD",
    )
    index = Column(
        Integer,
        nullable=False,
        comment="当天内第几个任务段（从0开始的序号）",
    )
    start_ts = Column(
        BigInteger,
        nullable=False,
        comment="任务开始时间的时间戳（秒）",
    )
    end_ts = Column(
        BigInteger,
        nullable=False,
        comment="任务结束时间的时间戳（秒）",
    )
    rtsp_url = Column(
        String(512),
        nullable=False,
        comment="完整RTSP回放地址（包含IP、通道、起止时间）",
    )
    ip = Column(
        String(64),
        index=True,
        nullable=True,
        comment="摄像头IP（从rtsp_url冗余解析，便于按IP查询）",
    )
    channel = Column(
        String(16),
        index=True,
        nullable=True,
        comment="通道编号（如 c1/c2/c3/c4，便于按通道查询）",
    )
    status = Column(
        String(32),
        default="pending",
        comment="任务状态：pending/playing/completed/failed 等",
    )
    screenshot_path = Column(
        String(512),
        nullable=True,
        comment="最近一次截图文件的相对路径（相对于 screenshots 目录）",
    )
    error = Column(
        String(512),
        nullable=True,
        comment="错误信息（最近一次失败原因）",
    )
    retry_count = Column(
        Integer,
        default=0,
        comment="已重试次数（最大3次）",
    )
    next_retry_at = Column(
        DateTime,
        nullable=True,
        comment="下次允许重试的时间（用于失败任务的重试调度）",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录最近更新时间（UTC）",
    )

    batch = relationship("TaskBatch", back_populates="tasks")
    screenshots = relationship("Screenshot", back_populates="task")


class Screenshot(Base):
    """截图表：记录每一次成功保存到磁盘的截图文件"""

    __tablename__ = "screenshots"
    __table_args__ = {"comment": "截图表：记录每一次成功保存到磁盘的截图文件"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        comment="关联的任务ID（外键：tasks.id）",
    )
    file_path = Column(
        String(512),
        nullable=False,
        comment="截图文件相对路径（相对于 screenshots 目录）",
    )
    hash_value = Column(
        String(64),
        nullable=True,
        comment="截图文件内容的哈希值（用于相似度去重，可能为空）",
    )
    is_duplicate = Column(
        Boolean,
        default=False,
        comment="是否为重复截图（true表示已被判定为重复）",
    )
    kept_path = Column(
        String(512),
        nullable=True,
        comment="去重后被保留的那张截图路径（如果当前为重复图）",
    )
    # YOLO 相关状态字段：用于异步车位变化检测
    yolo_status = Column(
        String(32),
        default="pending",
        nullable=False,
        comment="YOLO 检测状态：pending/processing/done/failed",
    )
    yolo_last_error = Column(
        String(512),
        nullable=True,
        comment="最近一次 YOLO 检测失败的错误信息（如有）",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="截图生成时间（UTC）",
    )

    task = relationship("Task", back_populates="screenshots")
    ocr = relationship("OcrResult", back_populates="screenshot", uselist=False)


class MinuteScreenshot(Base):
    """每分钟截图表：记录任务时间段内每一分钟的截图文件"""

    __tablename__ = "minute_screenshots"
    __table_args__ = {"comment": "每分钟截图表：记录任务时间段内每一分钟的截图文件"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
        comment="关联的任务ID（外键：tasks.id）",
    )
    minute_index = Column(
        Integer,
        nullable=False,
        comment="分钟索引（从0开始，表示第几分钟）",
    )
    start_ts = Column(
        BigInteger,
        nullable=False,
        index=True,
        comment="该分钟的开始时间戳（秒）",
    )
    end_ts = Column(
        BigInteger,
        nullable=False,
        index=True,
        comment="该分钟的结束时间戳（秒）",
    )
    file_path = Column(
        String(512),
        nullable=False,
        comment="截图文件相对路径（相对于 screenshots 目录）",
    )
    status = Column(
        String(32),
        default="pending",
        nullable=False,
        comment="生成状态：pending/processing/completed/failed",
    )
    error = Column(
        String(512),
        nullable=True,
        comment="错误信息（如果生成失败）",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录最近更新时间（UTC）",
    )

    task = relationship("Task", backref="minute_screenshots")

    __table_args__ = (
        Index("idx_task_minute", "task_id", "minute_index"),
        Index("idx_task_time", "task_id", "start_ts", "end_ts"),
    )


class OcrResult(Base):
    """OCR 识别结果表：记录每张截图上时间水印的识别/修正结果"""

    __tablename__ = "ocr_results"
    __table_args__ = {"comment": "OCR 识别结果表：记录每张截图上时间水印的识别/修正结果"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    screenshot_id = Column(
        Integer,
        ForeignKey("screenshots.id"),
        nullable=False,
        comment="对应的截图ID（外键：screenshots.id）",
    )
    detected_time = Column(
        String(19),
        nullable=True,
        comment="OCR 自动识别出的时间字符串（格式：YYYY-MM-DD HH:MM:SS）",
    )
    detected_timestamp = Column(
        BigInteger,
        nullable=True,
        comment="detected_time 对应的时间戳（秒或毫秒）",
    )
    confidence = Column(
        Float,
        nullable=True,
        comment="OCR 识别置信度（0.0~1.0，数值越大表示越可信）",
    )
    is_manual_corrected = Column(
        Boolean,
        default=False,
        comment="是否已被人工修正（True 表示 corrected_* 字段有效）",
    )
    corrected_time = Column(
        String(19),
        nullable=True,
        comment="人工修正后的时间字符串（格式：YYYY-MM-DD HH:MM:SS）",
    )
    corrected_timestamp = Column(
        BigInteger,
        nullable=True,
        comment="人工修正时间的时间戳",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录最近更新时间（UTC）",
    )

    screenshot = relationship("Screenshot", back_populates="ocr")


class AutoScheduleRule(Base):
    """自动排程规则表：定义每天定时自动生成/运行截图任务的规则"""

    __tablename__ = "auto_schedule_rules"
    __table_args__ = {"comment": "自动排程规则表：定义每天定时自动生成/运行截图任务的规则"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    name = Column(
        String(128),
        nullable=True,
        comment="规则名称（可选，用于在界面上区分不同规则）",
    )
    use_today = Column(
        Boolean,
        default=True,
        comment="是否使用当天日期（True=当天，False=使用 custom_date）",
    )
    custom_date = Column(
        String(10),
        nullable=True,
        comment="自定义日期（当 use_today=False 时生效，格式：YYYY-MM-DD）",
    )
    base_rtsp = Column(
        String(512),
        nullable=False,
        comment="RTSP 基础地址（不含通道和时间段部分）",
    )
    channel = Column(
        String(16),
        nullable=False,
        comment="通道编号（c1-c4）",
    )
    interval_minutes = Column(
        Integer,
        default=10,
        comment="截图间隔分钟数（例如：10表示每10分钟一个任务段）",
    )
    trigger_time = Column(
        String(5),
        nullable=False,
        comment="每天触发时间（HH:mm格式，如“18:00”）",
    )
    is_enabled = Column(
        Boolean,
        default=True,
        comment="是否启用该规则（False 时不再自动触发）",
    )
    last_executed_at = Column(
        DateTime,
        nullable=True,
        comment="上次实际执行时间（UTC）",
    )
    execution_count = Column(
        Integer,
        default=0,
        comment="该规则累计已执行次数",
    )
    last_execution_status = Column(
        String(32),
        nullable=True,
        comment="上次执行状态（success/failed 等）",
    )
    last_execution_error = Column(
        String(512),
        nullable=True,
        comment="上次执行失败时的错误信息",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录最近更新时间（UTC）",
    )


class NvrConfig(Base):
    """NVR基础配置表：存储NVR的基本信息"""

    __tablename__ = "nvr_configs"
    __table_args__ = {"comment": "NVR基础配置表：存储NVR的基本信息"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    nvr_ip = Column(
        String(64),
        index=True,
        nullable=False,
        unique=True,
        comment="NVR IP地址",
    )
    parking_name = Column(
        String(128),
        nullable=False,
        comment="车场名称",
    )
    nvr_username = Column(
        String(64),
        nullable=False,
        comment="NVR账号",
    )
    nvr_password = Column(
        String(128),
        nullable=False,
        comment="NVR密码",
    )
    nvr_port = Column(
        Integer,
        default=554,
        nullable=False,
        comment="NVR端口",
    )
    db_host = Column(
        String(64),
        nullable=True,
        comment="数据库地址（用于查询车位坐标）",
    )
    db_user = Column(
        String(64),
        nullable=True,
        comment="数据库账号",
    )
    db_password = Column(
        String(128),
        nullable=True,
        comment="数据库密码",
    )
    db_port = Column(
        Integer,
        default=3306,
        nullable=True,
        comment="数据库端口",
    )
    db_name = Column(
        String(64),
        nullable=True,
        comment="数据库名称",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录最近更新时间（UTC）",
    )

    channels = relationship("ChannelConfig", back_populates="nvr_config", cascade="all, delete-orphan")


class ChannelConfig(Base):
    """通道配置表：存储每个通道的详细信息"""

    __tablename__ = "channel_configs"
    __table_args__ = {"comment": "通道配置表：存储每个通道的详细信息"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    nvr_config_id = Column(
        Integer,
        ForeignKey("nvr_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联的NVR配置ID",
    )
    channel_code = Column(
        String(16),
        nullable=False,
        comment="通道编号（如 c1/c2/c3/c4）",
    )
    camera_ip = Column(
        String(64),
        nullable=True,
        comment="摄像头IP地址",
    )
    camera_name = Column(
        String(128),
        nullable=True,
        comment="摄像头名称",
    )
    camera_sn = Column(
        String(64),
        nullable=True,
        index=True,
        comment="摄像头SN",
    )
    track_space = Column(
        String(2048),
        nullable=True,
        comment="识别停车区域坐标（track_space 原始值）",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录最近更新时间（UTC）",
    )

    nvr_config = relationship("NvrConfig", back_populates="channels")
    parking_spaces_rel = relationship("ParkingSpace", back_populates="channel_config", cascade="all, delete-orphan")


class ParkingSpace(Base):
    """车位信息表：存储每个通道关联的车位编号和坐标"""

    __tablename__ = "parking_spaces"
    __table_args__ = {"comment": "车位信息表：存储每个通道关联的车位编号和坐标"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    channel_config_id = Column(
        Integer,
        ForeignKey("channel_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联的通道配置ID",
    )
    space_name = Column(
        String(64),
        nullable=False,
        comment="车位编号（如 GXSL091）",
    )
    bbox_x1 = Column(
        Integer,
        nullable=False,
        comment="边界框左上角X坐标",
    )
    bbox_y1 = Column(
        Integer,
        nullable=False,
        comment="边界框左上角Y坐标",
    )
    bbox_x2 = Column(
        Integer,
        nullable=False,
        comment="边界框右下角X坐标",
    )
    bbox_y2 = Column(
        Integer,
        nullable=False,
        comment="边界框右下角Y坐标",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录最近更新时间（UTC）",
    )

    channel_config = relationship("ChannelConfig", back_populates="parking_spaces_rel")


class ParkingChange(Base):
    """车位变化明细表：记录每张截图中每个车位的占用状态变化"""

    __tablename__ = "parking_changes"
    __table_args__ = {"comment": "车位变化明细表：记录每张截图中每个车位的占用状态变化"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
        comment="关联的任务ID（外键：tasks.id）",
    )
    screenshot_id = Column(
        Integer,
        ForeignKey("screenshots.id"),
        nullable=False,
        index=True,
        comment="关联的截图ID（外键：screenshots.id）",
    )
    channel_config_id = Column(
        Integer,
        ForeignKey("channel_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的通道配置ID（外键：channel_configs.id）",
    )
    space_id = Column(
        Integer,
        ForeignKey("parking_spaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的车位ID（外键：parking_spaces.id）",
    )
    space_name = Column(
        String(64),
        nullable=True,
        comment="车位编号（冗余字段，用于直接说明是哪一个车位发生变化）",
    )
    prev_occupied = Column(
        Boolean,
        nullable=True,
        comment="上一张图中该车位是否有车（NULL 表示无历史记录）",
    )
    curr_occupied = Column(
        Boolean,
        nullable=False,
        comment="当前截图中该车位是否有车（经过多帧平滑+特征比对后的可信最终状态）",
    )
    change_type = Column(
        String(32),
        nullable=True,
        comment="变化类型：arrive（进车）/leave（离开）/unknown（无法明确）",
    )
    detection_confidence = Column(
        Float,
        nullable=True,
        comment="检测置信度（0.0-1.0），表示检测到车辆的置信度或特征相似度得分",
    )
    vehicle_features = Column(
        JSON,
        nullable=True,
        comment="车辆视觉特征（JSON格式）：包含HSV直方图、宽高比、雨刮等特征，用于车辆重识别",
    )
    detected_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="变化判定时间",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )


class ParkingChangeSnapshot(Base):
    """车位变化快照表：每条记录代表某张截图上存在至少一个车位变化"""

    __tablename__ = "parking_change_snapshots"
    __table_args__ = {"comment": "车位变化快照表：用于快速查询有车位变化的截图列表"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="主键ID",
    )
    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
        comment="关联的任务ID（外键：tasks.id）",
    )
    screenshot_id = Column(
        Integer,
        ForeignKey("screenshots.id"),
        nullable=False,
        index=True,
        comment="关联的截图ID（外键：screenshots.id）",
    )
    channel_config_id = Column(
        Integer,
        ForeignKey("channel_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的通道配置ID（外键：channel_configs.id）",
    )
    ip = Column(
        String(64),
        nullable=True,
        index=True,
        comment="摄像机 IP（冗余，用于检索和展示）",
    )
    channel_code = Column(
        String(16),
        nullable=True,
        index=True,
        comment="通道编码（如 c1/c2/c3/c4，冗余用于检索和展示）",
    )
    parking_name = Column(
        String(128),
        nullable=True,
        comment="车场名称（冗余自 NvrConfig.parking_name）",
    )
    change_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="本次截图中发生变化的车位数量",
    )
    detected_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="变化判定时间",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="记录创建时间（UTC）",
    )

