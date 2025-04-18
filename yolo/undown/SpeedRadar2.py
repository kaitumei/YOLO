import cv2  # 导入OpenCV库用于图像处理
from tracker2 import *  # 导入自定义的欧氏距离跟踪器
import numpy as np  # 导入数值计算库
end = 0  # 程序结束标志

# 创建欧氏距离跟踪器对象
tracker = EuclideanDistTracker()

# 视频捕获对象初始化
cap = cv2.VideoCapture(r"F:/CV-ML/YOLO/Test/Vehicle-Speed-Estimation-and-Detecting-Overspeeding-main/test.mp4")
f = 20  # 帧率相关参数
w = int(1000/(f-1))  # 计算等待时间参数

# 初始化背景减除器（运动检测）
object_detector = cv2.createBackgroundSubtractorMOG2(history=None,varThreshold=None)

# 定义形态学操作核（用于图像处理）
kernalOp = np.ones((3,3),np.uint8)  # 开运算核
kernalOp2 = np.ones((5,5),np.uint8) 
kernalCl = np.ones((11,11),np.uint8)  # 闭运算核
fgbg = cv2.createBackgroundSubtractorMOG2(detectShadows=True)  # 带阴影检测的背景减除器
kernal_e = np.ones((5,5),np.uint8)  # 腐蚀操作核

while True:
    ret,frame = cap.read()
    if not ret:  # 视频读取结束判断
        break
    frame = cv2.resize(frame, None, fx=0.5, fy=0.5)  # 调整帧尺寸
    height,width,_ = frame.shape  # 获取帧尺寸

    # 提取感兴趣区域(ROI)
    roi = frame[50:540,200:960]  # 裁剪特定区域进行分析

    # 方法1：基础背景减除
    mask = object_detector.apply(roi)
    _, mask = cv2.threshold(mask, 250, 255, cv2.THRESH_BINARY)

    # 方法2：增强型背景减除（实际使用的方法）
    fgmask = fgbg.apply(roi)  # 应用背景减除
    ret, imBin = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)  # 二值化处理
    mask1 = cv2.morphologyEx(imBin, cv2.MORPH_OPEN, kernalOp)  # 开运算去噪
    mask2 = cv2.morphologyEx(mask1, cv2.MORPH_CLOSE, kernalCl)  # 闭运算填充空洞
    e_img = cv2.erode(mask2, kernal_e)  # 腐蚀操作细化边缘

    # 轮廓检测
    contours,_ = cv2.findContours(e_img,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    detections = []  # 存储检测到的目标

    # 筛选有效轮廓
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000:  # 面积阈值过滤小目标
            x,y,w,h = cv2.boundingRect(cnt)  # 获取边界框
            cv2.rectangle(roi,(x,y),(x+w,y+h),(0,255,0),3)  # 绘制绿色边界框
            detections.append([x,y,w,h])  # 记录检测结果

    # 目标跟踪
    boxes_ids = tracker.update(detections)  # 更新跟踪器
    for box_id in boxes_ids:
        x,y,w,h,id = box_id

        # 根据速度显示不同颜色
        if tracker.getsp(id) < tracker.limit():  # 正常速度
            cv2.putText(roi, f"{id} {tracker.getsp(id)}", (x,y-15), 
                       cv2.FONT_HERSHEY_PLAIN, 1, (255,255,0), 2)  # 黄字显示
            cv2.rectangle(roi, (x, y), (x + w, y + h), (0, 255, 0), 3)
        else:  # 超速情况
            cv2.putText(roi, f"{id} {tracker.getsp(id)}", (x, y-15),
                       cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 2)  # 红字显示
            cv2.rectangle(roi, (x, y), (x + w, y + h), (0, 165, 255), 3)

        # 超速抓拍逻辑
        s = tracker.getsp(id)
        if tracker.f[id] == 1 and s != 0:
            tracker.capture(roi, x, y, h, w, s, id)

    # 绘制测速参考线
    line_params = [
        ((0, 410), (960, 410)),  # 上方水平线对
        ((0, 430), (960, 430)),
        ((0, 235), (960, 235)),  # 下方水平线对
        ((0, 255), (960, 255))
    ]
    for (start, end) in line_params:
        cv2.line(roi, start, end, (0, 0, 255), 2)  # 红色参考线

    # 显示处理结果
    cv2.imshow("ROI", roi)

    # 退出控制
    key = cv2.waitKey(w-10)
    if key == 27:  # ESC键退出
        tracker.end()
        end = 1
        break

# 资源释放
if end != 1:
    tracker.end()
cap.release()
cv2.destroyAllWindows()