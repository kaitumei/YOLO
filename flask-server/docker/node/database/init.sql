-- 选择数据库
USE hytt;

-- 车辆预约表
CREATE TABLE IF NOT EXISTS vehicle_appointments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  license_plate VARCHAR(20) NOT NULL COMMENT '车牌号码',
  vehicle_type VARCHAR(50) COMMENT '车辆类型',
  name VARCHAR(50) NOT NULL COMMENT '姓名',
  phone VARCHAR(20) NOT NULL COMMENT '电话',
  appointment_date DATE NOT NULL COMMENT '预约日期',
  appointment_time TIME NOT NULL COMMENT '预约时间',
  purpose VARCHAR(200) COMMENT '来访目的',
  status VARCHAR(20) NOT NULL DEFAULT '待审核' COMMENT '状态',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME COMMENT '更新时间',
  INDEX idx_license_plate (license_plate),
  INDEX idx_phone (phone),
  INDEX idx_appointment_date (appointment_date),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='车辆预约表';

-- 轮播图表
CREATE TABLE IF NOT EXISTS banners (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(100) COMMENT '轮播图标题',
  image_url VARCHAR(255) NOT NULL COMMENT '图片URL',
  link_url VARCHAR(255) COMMENT '链接URL',
  sort_order INT DEFAULT 0 COMMENT '排序顺序',
  status TINYINT DEFAULT 1 COMMENT '状态：0-禁用，1-启用',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME COMMENT '更新时间',
  INDEX idx_status (status),
  INDEX idx_sort (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='轮播图表';

-- 公告信息表
CREATE TABLE IF NOT EXISTS notices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(100) NOT NULL COMMENT '公告标题',
  content TEXT COMMENT '公告内容',
  publish_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间',
  end_time DATETIME COMMENT '结束时间',
  is_important TINYINT DEFAULT 0 COMMENT '是否重要：0-普通，1-重要',
  status TINYINT DEFAULT 1 COMMENT '状态：0-禁用，1-启用',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME COMMENT '更新时间',
  INDEX idx_status (status),
  INDEX idx_publish_time (publish_time),
  INDEX idx_important (is_important)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公告信息表';

-- 插入车辆预约测试数据
INSERT INTO vehicle_appointments (license_plate, vehicle_type, name, phone, appointment_date, appointment_time, purpose, status, create_time) VALUES
('京A88888', '轿车', '王五', '13700137000', DATE_ADD(CURDATE(), INTERVAL 1 DAY), '10:00:00', '商务洽谈', '待审核', NOW()),
('粤B66666', 'SUV', '赵六', '13600136000', DATE_ADD(CURDATE(), INTERVAL 2 DAY), '14:30:00', '参观访问', '已确认', NOW());

INSERT INTO vehicle_appointments 
(license_plate, vehicle_type, name, phone, appointment_date, appointment_time, purpose, status) 
VALUES 
('测B54321', 'SUV', '测试用户2', '13999999999', CURDATE(), '16:30:00', '功能测试', '待审核');

-- 插入轮播图测试数据
INSERT INTO banners (title, image_url, link_url, sort_order, status, create_time) VALUES
('园区欢迎您', '/static/images/banner1.jpg', '', 1, 1, NOW()),
('预约流程指南', '/static/images/banner2.jpg', '/pages/guide/index', 2, 1, NOW()),
('安全须知', '/static/images/banner3.jpg', '/pages/safety/index', 3, 1, NOW());

-- 插入公告信息测试数据
INSERT INTO notices (title, content, publish_time, is_important, status, create_time) VALUES
('系统升级通知', '尊敬的用户，我们将于本周六凌晨2:00-4:00进行系统维护，期间预约功能可能暂时无法使用，给您带来不便敬请谅解。', NOW(), 1, 1, NOW()),
('入园新规实施', '即日起，所有入园车辆需提前3天预约，请各位访客提前安排行程。', DATE_SUB(NOW(), INTERVAL 2 DAY), 0, 1, NOW()),
('五一假期开放安排', '五一劳动节期间（5月1日-5月5日）园区正常开放，但请注意可能出现人流量大的情况，建议错峰出行。', DATE_SUB(NOW(), INTERVAL 5 DAY), 0, 1, NOW());

GRANT SELECT, INSERT, UPDATE, DELETE ON hytt.vehicle_appointments TO 'HYTT'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hytt.banners TO 'HYTT'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hytt.notices TO 'HYTT'@'%';
FLUSH PRIVILEGES; 