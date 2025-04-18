const express = require('express');
const router = express.Router();
const { query, mockData } = require('../config/db');

// 创建缓存实例，添加错误处理，如果node-cache不可用则使用简单的内存缓存实现
let noticeCache;
try {
  const NodeCache = require('node-cache');
  noticeCache = new NodeCache({ stdTTL: 180, checkperiod: 60 }); // 减少缓存时间到3分钟
  console.log('成功初始化node-cache');
} catch (error) {
  console.warn('node-cache模块不可用，使用简单缓存实现');
  // 简单的内存缓存实现
  noticeCache = {
    data: new Map(),
    timeouts: new Map(),
    get: function(key) {
      return this.data.get(key);
    },
    set: function(key, value, ttl = 1800) {
      this.data.set(key, value);
      
      // 清除之前的timeout
      if (this.timeouts.has(key)) {
        clearTimeout(this.timeouts.get(key));
      }
      
      // 设置新的过期时间
      if (ttl > 0) {
        const timeout = setTimeout(() => {
          this.data.delete(key);
          this.timeouts.delete(key);
        }, ttl * 1000);
        this.timeouts.set(key, timeout);
      }
    },
    flushAll: function() {
      this.data.clear();
      
      // 清除所有超时
      this.timeouts.forEach(timeout => clearTimeout(timeout));
      this.timeouts.clear();
    }
  };
}

// 清除缓存的辅助函数
function clearCache() {
  try {
    console.log('清除公告缓存');
    noticeCache.flushAll();
    console.log('公告缓存已清除');
  } catch (error) {
    console.error('清除缓存失败:', error);
  }
}

// 输出当前路由模块已加载
console.log('公告路由模块已加载');

// 获取所有启用的公告（分页）
router.get('/', async (req, res) => {
  try {
    console.log('收到获取公告列表请求');
    const page = parseInt(req.query.page) || 1;
    const pageSize = parseInt(req.query.pageSize) || 10;
    const offset = (page - 1) * pageSize;
    
    // 缓存键
    const cacheKey = `notices_page_${page}_size_${pageSize}`;
    
    // 尝试从缓存获取
    const cachedData = noticeCache.get(cacheKey);
    if (cachedData) {
      console.log(`从缓存返回公告列表，页码: ${page}, 每页条数: ${pageSize}`);
      return res.json(cachedData);
    }
    
    // 获取总记录数
    const countResult = await query(
      'SELECT COUNT(*) as total FROM notices WHERE status = 1 AND (end_time IS NULL OR end_time > NOW())'
    );
    const total = countResult && countResult[0] ? countResult[0].total : 0;
    
    // 获取分页数据
    const notices = await query(
      `SELECT id, title, SUBSTRING(content, 1, 100) as content_preview, 
       publish_time, is_important, DATE_FORMAT(publish_time, '%Y-%m-%d') as date 
       FROM notices 
       WHERE status = 1 AND (end_time IS NULL OR end_time > NOW()) 
       ORDER BY is_important DESC, publish_time DESC 
       LIMIT ?, ?`,
      [parseInt(offset, 10), parseInt(pageSize, 10)]
    );
    
    const result = {
      total,
      page,
      pageSize,
      list: notices || []
    };
    
    // 存入缓存
    noticeCache.set(cacheKey, result);
    
    res.json(result);
  } catch (error) {
    console.error('获取公告列表失败:', error);
    // 出错时返回空数组
    const result = {
      total: 0,
      page: 1,
      pageSize: 10,
      list: []
    };
    res.json(result);
  }
});

// 获取最新公告（首页展示用）
router.get('/latest', async (req, res) => {
  try {
    // 增加CORS头，确保微信小程序可以访问
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
    
    console.log('收到获取最新公告请求');
    const limit = parseInt(req.query.limit) || 5;
    const forceRefresh = req.query.force === 'true';
    console.log(`获取最新公告，限制数量: ${limit}, 强制刷新: ${forceRefresh}`);
    console.log(`请求参数:`, req.query);
    
    // 始终清除缓存，强制从数据库获取最新数据
    clearCache();
    
    // 简化SQL查询，减少复杂度，注意LIMIT参数的处理方式
    try {
      // 直接使用数字而不是参数绑定方式处理LIMIT
      const sql = `SELECT id, title, content, publish_time, is_important
         FROM notices 
         WHERE status = 1
         ORDER BY is_important DESC, publish_time DESC 
         LIMIT ${limit}`;
         
      console.log('执行的SQL:', sql);
      
      const notices = await query(sql, []);
      
      console.log('数据库查询结果:', notices);
      console.log('数据长度:', notices ? notices.length : 0);
      
      // 不再提供测试数据，如果没有数据则返回空数组
      if (!notices || notices.length === 0) {
        console.log('数据库中没有公告数据，返回空数组');
        return res.json([]);
      }
      
      // 处理公告数据
      const processedNotices = notices.map(notice => ({
        id: notice.id,
        title: notice.title,
        content_preview: notice.content 
          ? notice.content.substring(0, 100) + (notice.content.length > 100 ? '...' : '') 
          : '',
        date: notice.publish_time ? new Date(notice.publish_time).toISOString().split('T')[0] : new Date().toISOString().split('T')[0],
        is_important: notice.is_important === 1 || notice.is_important === true
      }));
      
      console.log('处理后的公告数据:', JSON.stringify(processedNotices));
      console.log(`成功获取公告 ${processedNotices.length} 条`);
      
      // 返回经过处理的公告数据
      res.json(processedNotices);
    } catch (sqlError) {
      console.error('SQL执行错误:', sqlError);
      
      // 尝试使用备用查询方法
      console.log('尝试使用备用查询方法...');
      
      // 备用查询：不使用参数绑定
      const allNotices = await query('SELECT * FROM notices WHERE status = 1 ORDER BY is_important DESC, publish_time DESC');
      console.log(`获取到所有公告: ${allNotices ? allNotices.length : 0}条`);
      
      // 在JS中处理LIMIT
      const limitedNotices = allNotices ? allNotices.slice(0, limit) : [];
      
      if (!limitedNotices || limitedNotices.length === 0) {
        console.log('备用查询无结果，返回空数组');
        return res.json([]);
      }
      
      // 处理公告数据
      const processedNotices = limitedNotices.map(notice => ({
        id: notice.id,
        title: notice.title,
        content_preview: notice.content 
          ? notice.content.substring(0, 100) + (notice.content.length > 100 ? '...' : '') 
          : '',
        date: notice.publish_time ? new Date(notice.publish_time).toISOString().split('T')[0] : new Date().toISOString().split('T')[0],
        is_important: notice.is_important === 1 || notice.is_important === true
      }));
      
      console.log(`备用方法成功获取公告 ${processedNotices.length} 条`);
      res.json(processedNotices);
    }
  } catch (error) {
    console.error('获取最新公告失败:', error);
    console.error('详细错误信息:', error.stack);
    
    // 出错时返回空数组
    res.json([]);
  }
});

// 获取所有公告（管理端使用）
router.get('/all', async (req, res) => {
  try {
    console.log('收到获取所有公告请求（管理端）');
    const notices = await query(
      `SELECT id, title, SUBSTRING(content, 1, 100) as content_preview, 
       publish_time, end_time, is_important, status, create_time, update_time
       FROM notices 
       ORDER BY is_important DESC, publish_time DESC`
    );
    
    res.json(notices || []);
  } catch (error) {
    console.error('获取所有公告失败:', error);
    res.json([]); // 返回空数组而不是错误
  }
});

// 获取单个公告详情
router.get('/:id', async (req, res) => {
  try {
    console.log(`收到获取公告详情请求，ID: ${req.params.id}`);
    
    // 缓存键
    const cacheKey = `notice_detail_${req.params.id}`;
    
    // 尝试从缓存获取
    const cachedData = noticeCache.get(cacheKey);
    if (cachedData) {
      console.log('从缓存返回公告详情');
      return res.json(cachedData);
    }
    
    const notice = await query(
      `SELECT id, title, content, SUBSTRING(content, 1, 100) as content_preview, 
       DATE_FORMAT(publish_time, '%Y-%m-%d') as date, is_important, status 
       FROM notices WHERE id = ? AND status = 1`,
      [req.params.id]
    );
    
    if (notice && notice.length > 0) {
      const noticeDetail = notice[0];
      
      // 处理公告数据
      noticeDetail.is_important = noticeDetail.is_important === 1 || noticeDetail.is_important === true;
      
      // 存入缓存
      noticeCache.set(cacheKey, noticeDetail, 300); // 5分钟
      
      res.json(noticeDetail);
    } else {
      // 如果找不到公告，返回404
      res.status(404).json({ error: '公告不存在' });
    }
  } catch (error) {
    console.error('获取公告详情失败:', error);
    res.status(500).json({ error: '获取公告详情失败' });
  }
});

// 创建公告
router.post('/', async (req, res) => {
  try {
    console.log('收到创建公告请求');
    const { title, content, publish_time, end_time, is_important, status } = req.body;
    
    // 验证必填字段
    if (!title) {
      return res.status(400).json({ message: '公告标题不能为空' });
    }
    
    const result = await query(
      `INSERT INTO notices 
       (title, content, publish_time, end_time, is_important, status, create_time) 
       VALUES (?, ?, ?, ?, ?, ?, NOW())`,
      [
        title, 
        content, 
        publish_time || new Date(), 
        end_time, 
        is_important === undefined ? 0 : is_important, 
        status === undefined ? 1 : status
      ]
    );
    
    // 清除所有公告相关缓存
    clearCache();
    
    res.status(201).json({
      message: '公告创建成功',
      noticeId: result.insertId
    });
  } catch (error) {
    console.error('创建公告失败:', error);
    res.status(500).json({ message: '创建公告失败', error: error.message });
  }
});

// 更新公告
router.put('/:id', async (req, res) => {
  try {
    const noticeId = req.params.id;
    console.log(`收到更新公告请求，ID: ${noticeId}`);
    const { title, content, publish_time, end_time, is_important, status } = req.body;
    
    // 验证必填字段
    if (!title) {
      return res.status(400).json({ message: '公告标题不能为空' });
    }
    
    const result = await query(
      `UPDATE notices 
       SET title = ?, content = ?, publish_time = ?, end_time = ?, 
       is_important = ?, status = ?, update_time = NOW() 
       WHERE id = ?`,
      [title, content, publish_time, end_time, is_important, status, noticeId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '公告不存在' });
    }
    
    // 清除所有公告相关缓存
    clearCache();
    
    res.json({ message: '公告更新成功' });
  } catch (error) {
    console.error('更新公告失败:', error);
    res.status(500).json({ message: '更新公告失败', error: error.message });
  }
});

// 删除公告
router.delete('/:id', async (req, res) => {
  try {
    const noticeId = req.params.id;
    console.log(`收到删除公告请求，ID: ${noticeId}`);
    
    const result = await query('DELETE FROM notices WHERE id = ?', [noticeId]);
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '公告不存在' });
    }
    
    // 清除所有公告相关缓存
    clearCache();
    
    res.json({ message: '公告删除成功' });
  } catch (error) {
    console.error('删除公告失败:', error);
    res.status(500).json({ message: '删除公告失败', error: error.message });
  }
});

// 修改公告状态
router.patch('/:id/status', async (req, res) => {
  try {
    const noticeId = req.params.id;
    console.log(`收到修改公告状态请求，ID: ${noticeId}`);
    const { status } = req.body;
    
    if (status === undefined) {
      return res.status(400).json({ message: '状态不能为空' });
    }
    
    const result = await query(
      'UPDATE notices SET status = ?, update_time = NOW() WHERE id = ?',
      [status, noticeId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '公告不存在' });
    }
    
    // 清除所有公告相关缓存
    clearCache();
    
    res.json({ message: '公告状态更新成功' });
  } catch (error) {
    console.error('更新公告状态失败:', error);
    res.status(500).json({ message: '更新公告状态失败', error: error.message });
  }
});

// 状态检查接口，用于前端检测服务是否可用
router.get('/status', (req, res) => {
  res.json({
    status: 'ok',
    time: new Date().toISOString(),
    service: 'notices'
  });
});

module.exports = router; 