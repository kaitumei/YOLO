const express = require('express');
const router = express.Router();
const { query } = require('../config/db');

// 获取所有预约
router.get('/', async (req, res) => {
  try {
    const bookings = await query(`
      SELECT b.*, u.name as user_name, v.plate_number 
      FROM bookings b
      LEFT JOIN users u ON b.user_id = u.id
      LEFT JOIN vehicles v ON b.vehicle_id = v.id
    `);
    res.json(bookings);
  } catch (error) {
    res.status(500).json({ message: '获取预约失败', error: error.message });
  }
});

// 获取单个预约
router.get('/:id', async (req, res) => {
  try {
    const bookingId = req.params.id;
    const bookings = await query(`
      SELECT b.*, u.name as user_name, v.plate_number 
      FROM bookings b
      LEFT JOIN users u ON b.user_id = u.id
      LEFT JOIN vehicles v ON b.vehicle_id = v.id
      WHERE b.id = ?
    `, [bookingId]);
    
    if (bookings.length === 0) {
      return res.status(404).json({ message: '预约不存在' });
    }
    
    res.json(bookings[0]);
  } catch (error) {
    res.status(500).json({ message: '获取预约失败', error: error.message });
  }
});

// 获取用户的所有预约
router.get('/user/:userId', async (req, res) => {
  try {
    const userId = req.params.userId;
    const bookings = await query(`
      SELECT b.*, v.plate_number 
      FROM bookings b
      LEFT JOIN vehicles v ON b.vehicle_id = v.id
      WHERE b.user_id = ?
      ORDER BY b.booking_time DESC
    `, [userId]);
    
    res.json(bookings);
  } catch (error) {
    res.status(500).json({ message: '获取用户预约失败', error: error.message });
  }
});

// 创建新预约
router.post('/', async (req, res) => {
  try {
    const { 
      user_id, 
      vehicle_id, 
      booking_time, 
      service_type, 
      notes 
    } = req.body;
    
    if (!user_id || !vehicle_id || !booking_time || !service_type) {
      return res.status(400).json({ 
        message: '用户ID、车辆ID、预约时间和服务类型不能为空' 
      });
    }
    
    const result = await query(
      `INSERT INTO bookings 
       (user_id, vehicle_id, booking_time, service_type, status, notes, create_time) 
       VALUES (?, ?, ?, ?, 'pending', ?, NOW())`,
      [user_id, vehicle_id, booking_time, service_type, notes]
    );
    
    res.status(201).json({
      message: '预约创建成功',
      bookingId: result.insertId
    });
  } catch (error) {
    res.status(500).json({ message: '创建预约失败', error: error.message });
  }
});

// 更新预约状态
router.put('/:id/status', async (req, res) => {
  try {
    const bookingId = req.params.id;
    const { status } = req.body;
    
    if (!status) {
      return res.status(400).json({ message: '状态不能为空' });
    }
    
    // 验证状态值是否有效
    const validStatuses = ['pending', 'confirmed', 'completed', 'cancelled'];
    if (!validStatuses.includes(status)) {
      return res.status(400).json({ 
        message: '无效的状态值，必须是 pending, confirmed, completed 或 cancelled' 
      });
    }
    
    const result = await query(
      'UPDATE bookings SET status = ?, update_time = NOW() WHERE id = ?',
      [status, bookingId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '预约不存在' });
    }
    
    res.json({ message: '预约状态更新成功' });
  } catch (error) {
    res.status(500).json({ message: '更新预约状态失败', error: error.message });
  }
});

// 更新预约信息
router.put('/:id', async (req, res) => {
  try {
    const bookingId = req.params.id;
    const { 
      booking_time, 
      service_type, 
      notes 
    } = req.body;
    
    const result = await query(
      `UPDATE bookings 
       SET booking_time = ?, service_type = ?, notes = ?, update_time = NOW() 
       WHERE id = ?`,
      [booking_time, service_type, notes, bookingId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '预约不存在' });
    }
    
    res.json({ message: '预约更新成功' });
  } catch (error) {
    res.status(500).json({ message: '更新预约失败', error: error.message });
  }
});

// 删除预约
router.delete('/:id', async (req, res) => {
  try {
    const bookingId = req.params.id;
    
    const result = await query('DELETE FROM bookings WHERE id = ?', [bookingId]);
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '预约不存在' });
    }
    
    res.json({ message: '预约删除成功' });
  } catch (error) {
    res.status(500).json({ message: '删除预约失败', error: error.message });
  }
});

// 获取特定日期的所有预约
router.get('/date/:date', async (req, res) => {
  try {
    const date = req.params.date;
    const bookings = await query(`
      SELECT b.*, u.name as user_name, v.plate_number 
      FROM bookings b
      LEFT JOIN users u ON b.user_id = u.id
      LEFT JOIN vehicles v ON b.vehicle_id = v.id
      WHERE DATE(b.booking_time) = ?
      ORDER BY b.booking_time
    `, [date]);
    
    res.json(bookings);
  } catch (error) {
    res.status(500).json({ message: '获取预约失败', error: error.message });
  }
});

module.exports = router; 