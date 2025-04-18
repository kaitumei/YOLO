from enum import Enum


class PermissionEnum(Enum):
    BOARD = '板块'
    LOGS = '日志'
    VIEW_STATS = "查看统计数据"
    FRONT_USER = '前台用户'
    CMS_USER = '后台用户'
    VEHICLE_APPOINTMENT = '车辆预约'
    BANNER = '轮播图'
    NOTICE = '公告'


