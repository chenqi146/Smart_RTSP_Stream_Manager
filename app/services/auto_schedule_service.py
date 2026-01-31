"""自动调度规则业务逻辑层（Service Pattern）"""
from typing import Optional, Dict, Any, List
import re
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.repositories.auto_schedule_repository import AutoScheduleRepository
from models import AutoScheduleRule
from schemas.tasks import AutoScheduleRuleCreate, AutoScheduleRuleUpdate


class AutoScheduleService:
    """自动调度规则业务逻辑服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = AutoScheduleRepository(db)
    
    def validate_rule_data(self, rule_data: AutoScheduleRuleCreate) -> None:
        """验证规则数据"""
        # 验证日期选择
        if not rule_data.use_today and not rule_data.custom_date:
            raise HTTPException(
                status_code=400,
                detail="必须选择日期或勾选自动获取当日时间"
            )
        
        if rule_data.use_today and rule_data.custom_date:
            raise HTTPException(
                status_code=400,
                detail="勾选自动获取当日时间后不能填写自定义日期"
            )
        
        # 验证触发时间格式
        try:
            hour, minute = map(int, rule_data.trigger_time.split(":"))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
        except:
            raise HTTPException(
                status_code=400,
                detail="触发时间格式错误，应为HH:mm格式"
            )
        
        # 验证RTSP地址格式
        if not rule_data.base_rtsp.startswith("rtsp://"):
            raise HTTPException(
                status_code=400,
                detail="RTSP地址格式错误，应以rtsp://开头"
            )
        
        # 验证通道格式
        if not re.match(r"^c[1-9]\d*$", rule_data.channel.lower()):
            raise HTTPException(
                status_code=400,
                detail="通道格式错误，应为c1、c2、c3等格式"
            )
        
        # 验证间隔分钟数
        if rule_data.interval_minutes <= 0 or rule_data.interval_minutes > 1440:
            raise HTTPException(
                status_code=400,
                detail="间隔分钟数应在1-1440之间"
            )
    
    def generate_rule_name(self, rule_data: AutoScheduleRuleCreate) -> str:
        """自动生成规则名称"""
        if rule_data.name:
            return rule_data.name
        
        # 从RTSP地址提取IP
        ip_match = re.search(r"@([\d.]+)(?::\d+)?", rule_data.base_rtsp)
        ip = ip_match.group(1) if ip_match else "unknown"
        return f"{ip}_{rule_data.channel}_{rule_data.trigger_time}"
    
    def create_rule(self, rule_data: AutoScheduleRuleCreate) -> Dict[str, Any]:
        """创建规则"""
        # 验证数据
        self.validate_rule_data(rule_data)
        
        # 生成规则名称
        rule_name = self.generate_rule_name(rule_data)
        
        # 创建规则对象
        rule = AutoScheduleRule(
            name=rule_name,
            use_today=rule_data.use_today,
            custom_date=rule_data.custom_date if not rule_data.use_today else None,
            base_rtsp=rule_data.base_rtsp,
            channel=rule_data.channel,
            interval_minutes=rule_data.interval_minutes,
            trigger_time=rule_data.trigger_time,
            is_enabled=True,
        )
        
        # 保存到数据库
        rule = self.repository.create(rule)
        
        return {
            "id": rule.id,
            "message": "规则保存成功",
        }
    
    def get_all_rules(self) -> List[Dict[str, Any]]:
        """获取所有规则"""
        rules = self.repository.get_all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "use_today": r.use_today,
                "custom_date": r.custom_date,
                "base_rtsp": r.base_rtsp,
                "channel": r.channel,
                "interval_minutes": r.interval_minutes,
                "trigger_time": r.trigger_time,
                "is_enabled": r.is_enabled,
                "last_executed_at": (
                    r.last_executed_at.isoformat() + "Z"
                    if r.last_executed_at and r.last_executed_at.tzinfo is None
                    else r.last_executed_at.isoformat()
                ) if r.last_executed_at else None,
                "execution_count": r.execution_count,
                "last_execution_status": r.last_execution_status,
                "last_execution_error": r.last_execution_error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rules
        ]
    
    def update_rule(self, rule_id: int, rule_data: AutoScheduleRuleUpdate) -> Dict[str, str]:
        """更新规则"""
        rule = self.repository.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
        
        rule.is_enabled = rule_data.is_enabled
        self.repository.update(rule)
        
        return {"message": "规则更新成功"}
    
    def delete_rule(self, rule_id: int) -> Dict[str, str]:
        """删除规则"""
        rule = self.repository.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
        
        self.repository.delete(rule)
        return {"message": "规则删除成功"}
    
    def get_enabled_rules(self) -> List[AutoScheduleRule]:
        """获取所有启用的规则"""
        return self.repository.get_enabled_rules()
    
    def update_execution_info(
        self,
        rule_id: int,
        last_executed_at: Optional[datetime] = None,
        execution_count: Optional[int] = None,
        last_execution_status: Optional[str] = None,
        last_execution_error: Optional[str] = None,
    ) -> Optional[AutoScheduleRule]:
        """更新规则执行信息"""
        return self.repository.update_execution_info(
            rule_id=rule_id,
            last_executed_at=last_executed_at,
            execution_count=execution_count,
            last_execution_status=last_execution_status,
            last_execution_error=last_execution_error,
        )

