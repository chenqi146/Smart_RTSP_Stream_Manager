"""自动调度规则数据访问层（Repository Pattern）"""
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from models import AutoScheduleRule


class AutoScheduleRepository:
    """自动调度规则数据访问仓库"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== 基础 CRUD 操作 ====================
    
    def get_all(self) -> List[AutoScheduleRule]:
        """获取所有规则，按创建时间倒序"""
        return (
            self.db.query(AutoScheduleRule)
            .order_by(AutoScheduleRule.created_at.desc())
            .all()
        )
    
    def get_by_id(self, rule_id: int) -> Optional[AutoScheduleRule]:
        """根据 ID 获取规则"""
        return (
            self.db.query(AutoScheduleRule)
            .filter(AutoScheduleRule.id == rule_id)
            .first()
        )
    
    def get_enabled_rules(self) -> List[AutoScheduleRule]:
        """获取所有启用的规则"""
        return (
            self.db.query(AutoScheduleRule)
            .filter(AutoScheduleRule.is_enabled == True)
            .all()
        )
    
    def create(self, rule: AutoScheduleRule) -> AutoScheduleRule:
        """创建规则"""
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule
    
    def update(self, rule: AutoScheduleRule) -> AutoScheduleRule:
        """更新规则"""
        rule.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(rule)
        return rule
    
    def delete(self, rule: AutoScheduleRule) -> None:
        """删除规则"""
        self.db.delete(rule)
        self.db.commit()
    
    def update_execution_info(
        self,
        rule_id: int,
        last_executed_at: Optional[datetime] = None,
        execution_count: Optional[int] = None,
        last_execution_status: Optional[str] = None,
        last_execution_error: Optional[str] = None,
    ) -> Optional[AutoScheduleRule]:
        """更新规则执行信息"""
        rule = self.get_by_id(rule_id)
        if not rule:
            return None
        
        if last_executed_at is not None:
            rule.last_executed_at = last_executed_at
        if execution_count is not None:
            rule.execution_count = execution_count
        if last_execution_status is not None:
            rule.last_execution_status = last_execution_status
        if last_execution_error is not None:
            rule.last_execution_error = last_execution_error
        
        rule.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(rule)
        return rule

