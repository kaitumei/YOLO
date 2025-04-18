# import cv2
# import os
# from datetime import datetime
#
#
# def process_detection(model, input_path, output_folder):
#     # 执行推理
#     img = cv2.imread(input_path)
#     results = model(img)
#
#     # 生成结果文件名
#     timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
#     output_filename = f"result_{timestamp}.jpg"
#     output_path = os.path.join(output_folder, output_filename)
#
#     # 保存标注图片
#     annotated_img = results[0].plot()
#     cv2.imwrite(output_path, annotated_img)
#
#     # 解析检测结果
#     detected_objects = []
#     for box in results[0].boxes:
#         cls_id = int(box.cls[0])
#         confidence = round(float(box.conf[0]) * 100, 2)
#         x1, y1, x2, y2 = map(int, box.xyxy[0])
#         detected_objects.append({
#             "class": model.names[cls_id],
#             "confidence": f"{confidence}%",
#             "coordinates": [x1, y1, x2, y2]
#         })
#
#     return output_filename, detected_objects