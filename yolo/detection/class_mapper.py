"""
类别映射模块

此模块提供车辆和违规类别的映射功能。
"""

# 默认类别映射 (ID到英文名称)
DEFAULT_CLASSES = {
    0: "car",
    1: "bus",
    2: "tanker",
    3: "container_truck",
    4: "truck",
    5: "van",
    6: "pickup",
    7: "special_vehicle",
    8: "license_plate",
    9: "accident",
    10: "illegal_parking",
    11: "overspeed"
}

# 中英文类别名称映射
DEFAULT_CLASS_NAMES_ZH = {
    0: "小汽车",        # car
    1: "公交车",        # bus
    2: "油罐车",        # tanker
    3: "集装箱卡车",    # container_truck
    4: "卡车",          # truck
    5: "面包车",        # van
    6: "皮卡车",        # pickup
    7: "特种车辆",      # special_vehicle
    8: "车牌",          # license_plate
    9: "事故车",        # accident
    10: "违停车",       # illegal_parking
    11: "超速车"        # overspeed
}

def load_classes(classes_file="classes.txt"):
    """
    从文件加载类别
    
    参数:
        classes_file: 类别文件路径
        
    返回:
        类别字典 {id: class_name}
    """
    classes = {}
    try:
        with open(classes_file, 'r', encoding='utf-8') as f:
            for line in f.readlines():
                line = line.strip()
                if not line:
                    continue
                
                # 尝试处理两种格式: "0 car" 或 "car"
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    try:
                        # 格式为 "0 car"
                        class_id = int(parts[0])
                        class_name = parts[1].strip()
                        classes[class_id] = class_name
                    except ValueError:
                        # 如果第一部分不是数字，则整行作为类名
                        class_id = len(classes)
                        classes[class_id] = line
                else:
                    # 格式为 "car"
                    class_id = len(classes)
                    classes[class_id] = line
        
        print(f"加载类别文件成功，共 {len(classes)} 个类别: {classes}")
        return classes
    except Exception as e:
        print(f"加载类别文件失败: {e}，使用默认类别")
        return DEFAULT_CLASSES.copy()

def get_vehicle_class_name(class_id, use_chinese=True, custom_classes=None, custom_zh_classes=None):
    """
    获取车辆类别名称
    
    参数:
        class_id: 类别ID
        use_chinese: 是否使用中文名称
        custom_classes: 自定义类别映射
        custom_zh_classes: 自定义中文类别映射
        
    返回:
        类别名称
    """
    classes = custom_classes or DEFAULT_CLASSES
    zh_classes = custom_zh_classes or DEFAULT_CLASS_NAMES_ZH
    
    if use_chinese and class_id in zh_classes:
        return zh_classes.get(class_id)
    return classes.get(class_id, f"未知类别-{class_id}") 