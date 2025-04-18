const express = require('express');
const router = express.Router();
const { query } = require('../config/db');

// 获取所有用户
router.get('/', async (req, res) => {
  try {
    const users = await query('SELECT * FROM users');
    res.json(users);
  } catch (error) {
    res.status(500).json({ message: '获取用户失败', error: error.message });
  }
});

// 获取单个用户
router.get('/:id', async (req, res) => {
  try {
    const userId = req.params.id;
    const users = await query('SELECT * FROM users WHERE id = ?', [userId]);
    
    if (users.length === 0) {
      return res.status(404).json({ message: '用户不存在' });
    }
    
    res.json(users[0]);
  } catch (error) {
    res.status(500).json({ message: '获取用户失败', error: error.message });
  }
});

// 创建新用户
router.post('/', async (req, res) => {
  try {
    const { name, phone, openid } = req.body;
    
    if (!name || !phone) {
      return res.status(400).json({ message: '姓名和电话不能为空' });
    }
    
    const result = await query(
      'INSERT INTO users (name, phone, openid, create_time) VALUES (?, ?, ?, NOW())',
      [name, phone, openid]
    );
    
    res.status(201).json({
      message: '用户创建成功',
      userId: result.insertId
    });
  } catch (error) {
    res.status(500).json({ message: '创建用户失败', error: error.message });
  }
});

// 更新用户
router.put('/:id', async (req, res) => {
  try {
    const userId = req.params.id;
    const { name, phone } = req.body;
    
    const result = await query(
      'UPDATE users SET name = ?, phone = ?, update_time = NOW() WHERE id = ?',
      [name, phone, userId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '用户不存在' });
    }
    
    res.json({ message: '用户更新成功' });
  } catch (error) {
    res.status(500).json({ message: '更新用户失败', error: error.message });
  }
});

// 删除用户
router.delete('/:id', async (req, res) => {
  try {
    const userId = req.params.id;
    
    const result = await query('DELETE FROM users WHERE id = ?', [userId]);
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '用户不存在' });
    }
    
    res.json({ message: '用户删除成功' });
  } catch (error) {
    res.status(500).json({ message: '删除用户失败', error: error.message });
  }
});

// 通过openid查找用户
router.get('/openid/:openid', async (req, res) => {
  try {
    const openid = req.params.openid;
    const users = await query('SELECT * FROM users WHERE openid = ?', [openid]);
    
    if (users.length === 0) {
      return res.status(404).json({ message: '用户不存在' });
    }
    
    res.json(users[0]);
  } catch (error) {
    res.status(500).json({ message: '查找用户失败', error: error.message });
  }
});

module.exports = router; 