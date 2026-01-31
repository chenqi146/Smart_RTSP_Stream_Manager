"""自动调度规则路由模块"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from schemas.tasks import AutoScheduleRuleCreate, AutoScheduleRuleUpdate
from app.dependencies import get_db
from app.services.auto_schedule_service import AutoScheduleService

router = APIRouter(prefix="/api/auto-schedule", tags=["自动调度"])


# ==================== 规则管理 ====================

@router.get("/rules")
def list_auto_rules(db: Session = Depends(get_db)):
    """获取所有自动分配规则"""
    service = AutoScheduleService(db)
    return service.get_all_rules()


@router.post("/rules")
def create_auto_rule(
    rule_data: AutoScheduleRuleCreate,
    db: Session = Depends(get_db)
):
    """创建自动分配规则"""
    service = AutoScheduleService(db)
    return service.create_rule(rule_data)


@router.patch("/rules/{rule_id}")
def update_auto_rule(
    rule_id: int,
    rule_data: AutoScheduleRuleUpdate,
    db: Session = Depends(get_db)
):
    """更新规则启用状态"""
    service = AutoScheduleService(db)
    return service.update_rule(rule_id, rule_data)


@router.delete("/rules/{rule_id}")
def delete_auto_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """删除自动分配规则"""
    service = AutoScheduleService(db)
    return service.delete_rule(rule_id)

