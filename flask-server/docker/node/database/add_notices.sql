-- 添加一些公告数据到数据库
INSERT INTO notices (title, content, publish_time, end_time, is_important, status, create_time) 
VALUES 
('2025年入园预约系统正式上线', '尊敬的用户，2025年入园预约系统已正式上线，您可以通过本系统预约入园。如有任何问题，请联系客服。', NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY), 1, 1, NOW()),
('系统功能升级通知', '系统已完成功能升级，新增了车辆管理、预约统计等功能，欢迎使用。', NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY), 0, 1, NOW()),
('五一假期预约提示', '五一假期期间入园人数较多，请提前3-5天进行预约，感谢您的配合。', NOW(), DATE_ADD(NOW(), INTERVAL 15 DAY), 1, 1, NOW());

-- 查看已添加的公告
SELECT * FROM notices ORDER BY id DESC LIMIT 10; 