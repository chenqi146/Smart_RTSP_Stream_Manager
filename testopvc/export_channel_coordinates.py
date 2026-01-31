"""
从数据库导出所有通道的跟踪区域和车位坐标

将数据保存到 channel_coordinates/ 目录下，按通道组织：
- channel_coordinates/{ip}_{channel_code}.json

每个文件包含：
{
    "nvr_ip": "192.168.1.100",
    "parking_name": "车场名称",
    "channel_code": "c1",
    "channel_name": "通道名称",
    "track_space": "...",
    "parking_spaces": [
        {
            "space_name": "GXSL091",
            "bbox_x1": 150,
            "bbox_y1": 150,
            "bbox_x2": 250,
            "bbox_y2": 250
        }
    ]
}
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# 添加项目路径（testopvc 的父目录，即 Smart_RTSP_Stream_Manager）
CURRENT_DIR = Path(__file__).resolve().parent  # testopvc 目录
PROJECT_ROOT = CURRENT_DIR.parent  # Smart_RTSP_Stream_Manager 目录
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import SessionLocal
from models import NvrConfig, ChannelConfig, ParkingSpace


def export_all_channel_coordinates(output_dir: str = "channel_coordinates") -> Dict[str, Any]:
    """
    导出所有通道的坐标数据
    
    参数:
        output_dir: 输出目录（相对于 testopvc 目录）
    
    返回:
        统计信息
    """
    # 输出目录相对于当前脚本所在目录（testopvc）
    CURRENT_DIR = Path(__file__).resolve().parent
    output_path = CURRENT_DIR / output_dir
    output_path.mkdir(exist_ok=True)
    
    stats = {
        "total_nvr": 0,
        "total_channels": 0,
        "total_spaces": 0,
        "exported_files": [],
        "errors": []
    }
    
    with SessionLocal() as db:
        # 查询所有NVR配置
        nvr_configs = db.query(NvrConfig).all()
        stats["total_nvr"] = len(nvr_configs)
        
        for nvr in nvr_configs:
            try:
                # 查询该NVR下的所有通道
                channels = (
                    db.query(ChannelConfig)
                    .filter(ChannelConfig.nvr_config_id == nvr.id)
                    .all()
                )
                
                for channel in channels:
                    try:
                        stats["total_channels"] += 1
                        
                        # 优先从外部数据库查询原始bbox格式（如果是多边形）
                        spaces_data = []
                        original_bbox_data = {}
                        
                        # 如果通道有camera_sn和NVR有数据库配置，尝试从外部数据库查询原始bbox
                        if channel.camera_sn and nvr.db_host and nvr.db_user and nvr.db_password and nvr.db_name:
                            try:
                                import pymysql
                                ext_conn = pymysql.connect(
                                    host=nvr.db_host,
                                    user=nvr.db_user,
                                    password=nvr.db_password,
                                    port=nvr.db_port or 3306,
                                    database=nvr.db_name,
                                    charset='utf8mb4'
                                )
                                ext_cursor = ext_conn.cursor()
                                
                                sql = """
                                SELECT 
                                    name,
                                    JSON_EXTRACT(
                                        space_annotation_info,
                                        CONCAT('$[', idx - 1, '].bbox')
                                    ) AS bbox
                                FROM (
                                    SELECT 
                                        name,
                                        space_annotation_info,
                                        idx
                                    FROM parking_space_info_tbl
                                    JOIN JSON_TABLE(
                                        space_annotation_info,
                                        '$[*]' COLUMNS (
                                            idx FOR ORDINALITY,
                                            gun_camera_sn VARCHAR(64) PATH '$.gun_camera_sn'
                                        )
                                    ) AS jt
                                    WHERE jt.gun_camera_sn = %s
                                ) AS matched;
                                """
                                ext_cursor.execute(sql, (channel.camera_sn,))
                                ext_results = ext_cursor.fetchall()
                                
                                for row in ext_results:
                                    space_name, bbox_json = row
                                    if bbox_json:
                                        try:
                                            bbox = json.loads(bbox_json)
                                            original_bbox_data[space_name] = bbox
                                        except:
                                            pass
                                
                                ext_cursor.close()
                                ext_conn.close()
                            except Exception as e:
                                print(f"警告: 无法从外部数据库查询原始bbox ({nvr.nvr_ip}/{channel.channel_code}): {e}")
                        
                        # 查询该通道下的所有停车位（从本地数据库）
                        parking_spaces = (
                            db.query(ParkingSpace)
                            .filter(ParkingSpace.channel_config_id == channel.id)
                            .all()
                        )
                        stats["total_spaces"] += len(parking_spaces)
                        
                        # 构建停车位数据（优先使用原始bbox，否则使用本地数据库的坐标）
                        for space in parking_spaces:
                            space_data = {
                                "space_name": space.space_name,
                            }
                            
                            # 如果从外部数据库获取到原始bbox，使用原始格式
                            if space.space_name in original_bbox_data:
                                space_data["bbox"] = original_bbox_data[space.space_name]
                            else:
                                # 否则使用本地数据库的矩形坐标
                                space_data["bbox_x1"] = space.bbox_x1
                                space_data["bbox_y1"] = space.bbox_y1
                                space_data["bbox_x2"] = space.bbox_x2
                                space_data["bbox_y2"] = space.bbox_y2
                            
                            spaces_data.append(space_data)
                        
                        # 构建通道数据
                        channel_data = {
                            "nvr_ip": nvr.nvr_ip,
                            "parking_name": nvr.parking_name,
                            "channel_code": channel.channel_code,
                            "channel_name": channel.camera_name or "",
                            "camera_ip": channel.camera_ip or "",
                            "camera_sn": channel.camera_sn or "",
                            "track_space": channel.track_space or None,
                            "parking_spaces": spaces_data,
                        }
                        
                        # 生成文件名：{ip}_{channel_code}.json
                        # 清理IP地址中的特殊字符
                        safe_ip = nvr.nvr_ip.replace(".", "_").replace(":", "_")
                        safe_channel = channel.channel_code.lower().replace("/", "_")
                        filename = f"{safe_ip}_{safe_channel}.json"
                        filepath = output_path / filename
                        
                        # 保存到文件
                        with open(filepath, "w", encoding="utf-8") as f:
                            json.dump(channel_data, f, ensure_ascii=False, indent=2)
                        
                        stats["exported_files"].append({
                            "file": filename,
                            "nvr_ip": nvr.nvr_ip,
                            "channel": channel.channel_code,
                            "spaces_count": len(spaces_data),
                        })
                        
                        print(f"✓ 已导出: {filename} (NVR: {nvr.nvr_ip}, 通道: {channel.channel_code}, 车位: {len(spaces_data)}个)")
                        
                    except Exception as e:
                        error_msg = f"导出通道 {nvr.nvr_ip}/{channel.channel_code} 时出错: {e}"
                        stats["errors"].append(error_msg)
                        print(f"✗ {error_msg}")
                        
            except Exception as e:
                error_msg = f"处理NVR {nvr.nvr_ip} 时出错: {e}"
                stats["errors"].append(error_msg)
                print(f"✗ {error_msg}")
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="从数据库导出所有通道的跟踪区域和车位坐标",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导出到默认目录 channel_coordinates/
  python export_channel_coordinates.py
  
  # 导出到指定目录
  python export_channel_coordinates.py --output my_coordinates
        """
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="channel_coordinates",
        help="输出目录（默认: channel_coordinates）"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("开始导出通道坐标数据...")
    print("=" * 60)
    print()
    
    try:
        stats = export_all_channel_coordinates(args.output)
        
        print()
        print("=" * 60)
        print("导出完成！")
        print("=" * 60)
        print(f"NVR配置数量: {stats['total_nvr']}")
        print(f"通道数量: {stats['total_channels']}")
        print(f"车位总数: {stats['total_spaces']}")
        print(f"导出文件数: {len(stats['exported_files'])}")
        
        if stats["errors"]:
            print(f"\n错误数量: {len(stats['errors'])}")
            for error in stats["errors"]:
                print(f"  - {error}")
        
        print(f"\n所有文件已保存到: {Path(args.output).resolve()}")
        print("\n文件列表:")
        for item in stats["exported_files"]:
            print(f"  - {item['file']} (NVR: {item['nvr_ip']}, 通道: {item['channel']}, 车位: {item['spaces_count']}个)")
        
    except Exception as e:
        print(f"\n✗ 导出失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
