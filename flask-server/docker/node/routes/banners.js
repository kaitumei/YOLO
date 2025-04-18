const express = require('express');
const router = express.Router();
const { query } = require('../config/db');

// 检查是否有错误的URL作为路由路径
// 正常的路由路径应该是 '/', '/id', '/:id' 等形式
// 不应该包含完整URL (http:// 或 https://)

// 获取所有启用的轮播图
router.get('/', async (req, res) => {
  try {
    const banners = await query(
      'SELECT id, title, image_url, link_url FROM banners WHERE status = 1 ORDER BY sort_order ASC'
    );
    
    // 如果没有数据，提供默认轮播图
    if (!banners || banners.length === 0) {
      console.log('数据库中没有轮播图数据，提供默认数据');
      const defaultBanners = [
        {
          id: 1,
          title: '慧眼通途欢迎您',
          image_url: '/static/images/banner1.jpg',
          link_url: ''
        },
        {
          id: 2,
          title: '智能预约系统',
          image_url: '/static/images/banner2.jpg',
          link_url: ''
        }
      ];
      return res.json(defaultBanners);
    }
    
    // 确保image_url格式正确
    banners.forEach(banner => {
      // 处理从Flask CMS上传的图片路径
      if (banner.image_url && banner.image_url.startsWith('/static/uploads/banners/')) {
        // 提取文件名并使用Node.js服务器的路径
        const filename = banner.image_url.split('/').pop();
        banner.image_url = `/static/images/${filename}`;
      }
      // 如果image_url不是以/static开头，添加/static前缀
      else if (banner.image_url && !banner.image_url.startsWith('/static') && !banner.image_url.startsWith('http')) {
        banner.image_url = '/static' + (banner.image_url.startsWith('/') ? '' : '/') + banner.image_url;
      }
      
      // 记录处理后的图片路径
      console.log(`轮播图 ${banner.id} 的图片路径: ${banner.image_url}`);
    });
    
    res.json(banners || []);
  } catch (error) {
    console.error('获取轮播图失败:', error);
    // 出错时返回默认数据而非空数组
    const defaultBanners = [
      {
        id: 1,
        title: '慧眼通途欢迎您',
        image_url: '/static/images/banner1.jpg',
        link_url: ''
      },
      {
        id: 2,
        title: '智能预约系统',
        image_url: '/static/images/banner2.jpg',
        link_url: ''
      }
    ];
    res.json(defaultBanners);
  }
});

// 获取所有轮播图（包括启用和禁用）- 管理端使用
router.get('/all', async (req, res) => {
  try {
    const banners = await query(
      'SELECT id, title, image_url, link_url, sort_order, status, create_time, update_time FROM banners ORDER BY sort_order ASC'
    );
    
    // 确保image_url格式正确
    banners.forEach(banner => {
      // 如果image_url不是以/static开头，添加/static前缀
      if (banner.image_url && !banner.image_url.startsWith('/static') && !banner.image_url.startsWith('http')) {
        banner.image_url = '/static' + (banner.image_url.startsWith('/') ? '' : '/') + banner.image_url;
      }
    });
    
    res.json(banners);
  } catch (error) {
    res.status(500).json({ message: '获取轮播图失败', error: error.message });
  }
});

// 获取单个轮播图
router.get('/:id', async (req, res) => {
  try {
    const bannerId = req.params.id;
    const banners = await query('SELECT * FROM banners WHERE id = ?', [bannerId]);
    
    if (banners.length === 0) {
      return res.status(404).json({ message: '轮播图不存在' });
    }
    
    res.json(banners[0]);
  } catch (error) {
    res.status(500).json({ message: '获取轮播图详情失败', error: error.message });
  }
});

// 创建轮播图
router.post('/', async (req, res) => {
  try {
    const { title, image_url, link_url, sort_order, status } = req.body;
    
    // 验证必填字段
    if (!image_url) {
      return res.status(400).json({ message: '图片URL不能为空' });
    }
    
    const result = await query(
      `INSERT INTO banners 
       (title, image_url, link_url, sort_order, status, create_time) 
       VALUES (?, ?, ?, ?, ?, NOW())`,
      [title, image_url, link_url, sort_order || 0, status === undefined ? 1 : status]
    );
    
    res.status(201).json({
      message: '轮播图创建成功',
      bannerId: result.insertId
    });
  } catch (error) {
    res.status(500).json({ message: '创建轮播图失败', error: error.message });
  }
});

// 更新轮播图
router.put('/:id', async (req, res) => {
  try {
    const bannerId = req.params.id;
    const { title, image_url, link_url, sort_order, status } = req.body;
    
    // 验证必填字段
    if (!image_url) {
      return res.status(400).json({ message: '图片URL不能为空' });
    }
    
    const result = await query(
      `UPDATE banners 
       SET title = ?, image_url = ?, link_url = ?, sort_order = ?, status = ?, update_time = NOW() 
       WHERE id = ?`,
      [title, image_url, link_url, sort_order, status, bannerId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '轮播图不存在' });
    }
    
    res.json({ message: '轮播图更新成功' });
  } catch (error) {
    res.status(500).json({ message: '更新轮播图失败', error: error.message });
  }
});

// 删除轮播图
router.delete('/:id', async (req, res) => {
  try {
    const bannerId = req.params.id;
    
    const result = await query('DELETE FROM banners WHERE id = ?', [bannerId]);
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '轮播图不存在' });
    }
    
    res.json({ message: '轮播图删除成功' });
  } catch (error) {
    res.status(500).json({ message: '删除轮播图失败', error: error.message });
  }
});

// 修改轮播图状态
router.patch('/:id/status', async (req, res) => {
  try {
    const bannerId = req.params.id;
    const { status } = req.body;
    
    if (status === undefined) {
      return res.status(400).json({ message: '状态不能为空' });
    }
    
    const result = await query(
      'UPDATE banners SET status = ?, update_time = NOW() WHERE id = ?',
      [status, bannerId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '轮播图不存在' });
    }
    
    res.json({ message: '轮播图状态更新成功' });
  } catch (error) {
    res.status(500).json({ message: '更新轮播图状态失败', error: error.message });
  }
});

module.exports = router; 