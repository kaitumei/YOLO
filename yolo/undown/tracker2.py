# 导入必要库
import cv2  # OpenCV图像处理库
import math  # 数学计算库（用于距离计算）
import time  # 时间模块（用于速度计算）
import numpy as np  # 数值计算库
import os  # 操作系统接口（用于文件操作）

limit = 80  # 速度阈值（单位：公里/小时）

# 创建存储目录
traffic_record_folder_name = "D:\TrafficRecord"  # 主存储路径
if not os.path.exists(traffic_record_folder_name):
    os.makedirs(traffic_record_folder_name)  # 创建主目录
    os.makedirs(traffic_record_folder_name + "//exceeded")  # 超速车辆子目录

# 初始化记录文件
speed_record_file_location = traffic_record_folder_name + "//SpeedRecord.txt"
file = open(speed_record_file_location, "w")  # 以写入模式打开文件
file.write("ID \t SPEED\n------\t-------\n")  # 写入表头
file.close()


class EuclideanDistTracker:
    def __init__(self):
        # 目标跟踪相关属性
        self.center_points = {}  # 存储目标中心点坐标 {id: (cx, cy)}
        self.id_count = 0  # 自增ID计数器

        # 速度计算相关属性
        self.et = 0  # 经过时间
        self.s1 = np.zeros((1, 1000))  # 进入检测线时间记录
        self.s2 = np.zeros((1, 1000))  # 离开检测线时间记录
        self.s = np.zeros((1, 1000))  # 时间差存储

        # 状态标记
        self.f = np.zeros(1000)  # 抓拍触发标记
        self.capf = np.zeros(1000)  # 已抓拍标记

        # 统计计数器
        self.count = 0  # 总车辆计数
        self.exceeded = 0  # 超速车辆计数

    def update(self, objects_rect):
        """核心更新方法，处理目标检测框并跟踪"""
        objects_bbs_ids = []

        # 遍历每个检测到的目标框
        for rect in objects_rect:
            x, y, w, h = rect
            cx = (x + x + w) // 2  # 计算中心点x坐标
            cy = (y + y + h) // 2  # 计算中心点y坐标

            # 目标匹配标识
            same_object_detected = False

            # 遍历现有目标进行匹配
            for id, pt in self.center_points.items():
                # 计算欧氏距离（新旧中心点间距）
                dist = math.hypot(cx - pt[0], cy - pt[1])

                # 匹配成功条件（距离小于阈值）
                if dist < 70:
                    self.center_points[id] = (cx, cy)  # 更新中心点
                    objects_bbs_ids.append([x, y, w, h, id])
                    same_object_detected = True

                    # 速度检测线逻辑（上方检测线范围410-430）
                    if 410 <= y <= 430:
                        self.s1[0, id] = time.time()  # 记录进入时间

                    # 下方检测线范围235-255
                    if 235 <= y <= 255:
                        self.s2[0, id] = time.time()  # 记录离开时间
                        self.s[0, id] = self.s2[0, id] - self.s1[0, id]  # 计算时间差

                    # 触发抓拍条件（车辆完全通过检测区域）
                    if y < 235:
                        self.f[id] = 1  # 设置抓拍标志

            # 新目标处理
            if not same_object_detected:
                self.center_points[self.id_count] = (cx, cy)
                objects_bbs_ids.append([x, y, w, h, self.id_count])
                # 初始化新目标的计时器
                self.id_count += 1
                self.s[0, self.id_count] = 0
                self.s1[0, self.id_count] = 0
                self.s2[0, self.id_count] = 0

        # 清理无效目标
        new_center_points = {}
        for obj_bb_id in objects_bbs_ids:
            _, _, _, _, object_id = obj_bb_id
            new_center_points[object_id] = self.center_points[object_id]
        self.center_points = new_center_points.copy()

        return objects_bbs_ids

    def getsp(self, id):
        """速度计算方法：固定距离/时间差"""
        if self.s[0, id] != 0:
            s = 214.15 / self.s[0, id]  # 214.15为校准参数（单位转换系数）
        else:
            s = 0
        return int(s)

    def capture(self, img, x, y, h, w, sp, id):
        """超速抓拍方法"""
        if self.capf[id] == 0:  # 防止重复抓拍
            self.capf[id] = 1  # 设置已抓拍标记
            self.f[id] = 0  # 重置触发标记

            # 截取车辆区域（扩展5像素边界）
            crop_img = img[y - 5:y + h + 5, x - 5:x + w + 5]

            # 生成文件名
            n = f"{id}_speed_{sp}"
            file = f"{traffic_record_folder_name}//{n}.jpg"

            # 保存图片
            cv2.imwrite(file, crop_img)
            self.count += 1  # 总计数增加

            # 记录到文件
            with open(speed_record_file_location, "a") as filet:
                if sp > limit:
                    # 超速车辆特殊处理
                    file2 = f"{traffic_record_folder_name}//exceeded//{n}.jpg"
                    cv2.imwrite(file2, crop_img)
                    filet.write(f"{id} \t {sp}<---exceeded\n")
                    self.exceeded += 1
                else:
                    filet.write(f"{id} \t {sp}\n")

    def limit(self):
        """获取速度限制"""
        return limit

    def end(self):
        """生成统计报告"""
        with open(speed_record_file_location, "a") as file:
            file.write("\n-------------\nSUMMARY\n-------------\n")
            file.write(f"Total Vehicles :\t{self.count}\n")
            file.write(f"Exceeded speed limit :\t{self.exceeded}")
