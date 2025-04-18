-- 创建notices表
CREATE TABLE IF NOT EXISTS notices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  content TEXT,
  publish_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  end_time DATETIME NULL,
  is_important TINYINT(1) DEFAULT 0,
  status TINYINT(1) DEFAULT 1,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME ON UPDATE CURRENT_TIMESTAMP
);

-- 添加示例公告数据
INSERT INTO notices (title, content, is_important, status) VALUES 
('欢迎使用慧眼通途系统', '这是慧眼通途系统的欢迎信息，希望您使用愉快！', 1, 1),
('系统维护通知', '系统将于本周日凌晨2点-4点进行例行维护，敬请知悉。', 0, 1),
('功能更新公告', '我们最近更新了预约功能，使用更加便捷，欢迎体验！', 1, 1);

-- 创建banners表
CREATE TABLE IF NOT EXISTS banners (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255),
  image_url VARCHAR(255) NOT NULL,
  link_url VARCHAR(255),
  sort_order INT DEFAULT 0,
  status TINYINT(1) DEFAULT 1,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME ON UPDATE CURRENT_TIMESTAMP
);

-- 添加示例轮播图数据
INSERT INTO banners (title, image_url, link_url, sort_order, status) VALUES 
('慧眼通途欢迎您', '/static/images/banner1.jpg', '', 1, 1),
('智能预约系统', '/static/images/banner2.jpg', '', 2, 1); 