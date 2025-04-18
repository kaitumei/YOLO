const express = require('express');
const router = express.Router();
const { query } = require('../config/db');

// 获取所有车辆预约
router.get('/', async (req, res) => {
  try {
    const appointments = await query('SELECT * FROM vehicle_appointments ORDER BY appointment_date, appointment_time');
    res.json(appointments);
  } catch (error) {
    res.status(500).json({ message: '获取预约失败', error: error.message });
  }
});

// 获取单个预约详情
router.get('/:id', async (req, res) => {
  try {
    const appointmentId = req.params.id;
    const appointments = await query('SELECT * FROM vehicle_appointments WHERE id = ?', [appointmentId]);
    
    if (appointments.length === 0) {
      return res.status(404).json({ message: '预约不存在' });
    }
    
    res.json(appointments[0]);
  } catch (error) {
    res.status(500).json({ message: '获取预约详情失败', error: error.message });
  }
});

// 根据电话号码获取预约
router.get('/phone/:phone', async (req, res) => {
  try {
    const phone = req.params.phone;
    const appointments = await query(
      'SELECT * FROM vehicle_appointments WHERE phone = ? ORDER BY appointment_date DESC, appointment_time DESC',
      [phone]
    );
    res.json(appointments);
  } catch (error) {
    res.status(500).json({ message: '获取预约失败', error: error.message });
  }
});

// 根据车牌号获取预约
router.get('/license/:licensePlate', async (req, res) => {
  try {
    const licensePlate = req.params.licensePlate;
    const appointments = await query(
      'SELECT * FROM vehicle_appointments WHERE license_plate = ? ORDER BY appointment_date DESC, appointment_time DESC',
      [licensePlate]
    );
    res.json(appointments);
  } catch (error) {
    res.status(500).json({ message: '获取预约失败', error: error.message });
  }
});

// 根据日期获取预约
router.get('/date/:date', async (req, res) => {
  try {
    const date = req.params.date;
    const appointments = await query(
      'SELECT * FROM vehicle_appointments WHERE appointment_date = ? ORDER BY appointment_time',
      [date]
    );
    res.json(appointments);
  } catch (error) {
    res.status(500).json({ message: '获取预约失败', error: error.message });
  }
});

// 根据用户ID获取预约
router.get('/user/:userId', async (req, res) => {
  try {
    const userId = req.params.userId;
    const appointments = await query(
      'SELECT * FROM vehicle_appointments WHERE user_id = ? OR created_by = ? ORDER BY appointment_date DESC, appointment_time DESC',
      [userId, userId]
    );
    res.json(appointments);
  } catch (error) {
    res.status(500).json({ message: '获取预约失败', error: error.message });
  }
});

// 创建新预约
router.post('/', async (req, res) => {
  try {
    const { 
      license_plate,
      vehicle_type,
      name,
      phone,
      appointment_date,
      appointment_time,
      purpose
    } = req.body;
    
    // 验证必填字段
    if (!license_plate || !name || !phone || !appointment_date || !appointment_time) {
      return res.status(400).json({ 
        message: '车牌号、姓名、电话、预约日期和时间不能为空' 
      });
    }
    
    const result = await query(
      `INSERT INTO vehicle_appointments 
      (license_plate, vehicle_type, name, phone, appointment_date, appointment_time, purpose, status, create_time) 
      VALUES (?, ?, ?, ?, ?, ?, ?, '待审核', NOW())`,
      [license_plate, vehicle_type, name, phone, appointment_date, appointment_time, purpose]
    );
    
    res.status(201).json({
      message: '预约创建成功',
      appointmentId: result.insertId
    });
  } catch (error) {
    res.status(500).json({ message: '创建预约失败', error: error.message });
  }
});

// 更新预约状态
router.put('/:id/status', async (req, res) => {
  try {
    const appointmentId = req.params.id;
    const { status } = req.body;
    
    if (!status) {
      return res.status(400).json({ message: '状态不能为空' });
    }
    
    // 验证状态值是否有效
    const validStatuses = ['待审核', '已确认', '已完成', '已取消', '已拒绝'];
    if (!validStatuses.includes(status)) {
      return res.status(400).json({ 
        message: '无效的状态值，必须是待审核、已确认、已完成、已取消或已拒绝' 
      });
    }
    
    const result = await query(
      'UPDATE vehicle_appointments SET status = ?, update_time = NOW() WHERE id = ?',
      [status, appointmentId]
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
    const appointmentId = req.params.id;
    const { 
      license_plate,
      vehicle_type,
      name,
      phone,
      appointment_date,
      appointment_time,
      purpose
    } = req.body;
    
    // 验证必填字段
    if (!license_plate || !name || !phone || !appointment_date || !appointment_time) {
      return res.status(400).json({ 
        message: '车牌号、姓名、电话、预约日期和时间不能为空' 
      });
    }
    
    const result = await query(
      `UPDATE vehicle_appointments 
       SET license_plate = ?, vehicle_type = ?, name = ?, phone = ?, 
           appointment_date = ?, appointment_time = ?, purpose = ?, update_time = NOW() 
       WHERE id = ?`,
      [license_plate, vehicle_type, name, phone, appointment_date, appointment_time, purpose, appointmentId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '预约不存在' });
    }
    
    res.json({ message: '预约信息更新成功' });
  } catch (error) {
    res.status(500).json({ message: '更新预约信息失败', error: error.message });
  }
});

// 删除预约
router.delete('/:id', async (req, res) => {
  try {
    const appointmentId = req.params.id;
    
    const result = await query('DELETE FROM vehicle_appointments WHERE id = ?', [appointmentId]);
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '预约不存在' });
    }
    
    res.json({ message: '预约删除成功' });
  } catch (error) {
    res.status(500).json({ message: '删除预约失败', error: error.message });
  }
});

module.exports = router; 