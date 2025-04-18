const express = require('express');
const router = express.Router();
const { query } = require('../config/db');

// 获取所有车辆
router.get('/', async (req, res) => {
  try {
    const vehicles = await query('SELECT * FROM vehicles');
    res.json(vehicles);
  } catch (error) {
    res.status(500).json({ message: '获取车辆失败', error: error.message });
  }
});

// 获取单个车辆
router.get('/:id', async (req, res) => {
  try {
    const vehicleId = req.params.id;
    const vehicles = await query('SELECT * FROM vehicles WHERE id = ?', [vehicleId]);
    
    if (vehicles.length === 0) {
      return res.status(404).json({ message: '车辆不存在' });
    }
    
    res.json(vehicles[0]);
  } catch (error) {
    res.status(500).json({ message: '获取车辆失败', error: error.message });
  }
});

// 获取用户的所有车辆
router.get('/user/:userId', async (req, res) => {
  try {
    const userId = req.params.userId;
    const vehicles = await query('SELECT * FROM vehicles WHERE user_id = ?', [userId]);
    res.json(vehicles);
  } catch (error) {
    res.status(500).json({ message: '获取用户车辆失败', error: error.message });
  }
});

// 添加新车辆
router.post('/', async (req, res) => {
  try {
    const { user_id, plate_number, vehicle_type, brand, model } = req.body;
    
    if (!user_id || !plate_number) {
      return res.status(400).json({ message: '用户ID和车牌号不能为空' });
    }
    
    const result = await query(
      'INSERT INTO vehicles (user_id, plate_number, vehicle_type, brand, model, create_time) VALUES (?, ?, ?, ?, ?, NOW())',
      [user_id, plate_number, vehicle_type, brand, model]
    );
    
    res.status(201).json({
      message: '车辆添加成功',
      vehicleId: result.insertId
    });
  } catch (error) {
    res.status(500).json({ message: '添加车辆失败', error: error.message });
  }
});

// 更新车辆信息
router.put('/:id', async (req, res) => {
  try {
    const vehicleId = req.params.id;
    const { plate_number, vehicle_type, brand, model } = req.body;
    
    const result = await query(
      'UPDATE vehicles SET plate_number = ?, vehicle_type = ?, brand = ?, model = ?, update_time = NOW() WHERE id = ?',
      [plate_number, vehicle_type, brand, model, vehicleId]
    );
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '车辆不存在' });
    }
    
    res.json({ message: '车辆更新成功' });
  } catch (error) {
    res.status(500).json({ message: '更新车辆失败', error: error.message });
  }
});

// 删除车辆
router.delete('/:id', async (req, res) => {
  try {
    const vehicleId = req.params.id;
    
    const result = await query('DELETE FROM vehicles WHERE id = ?', [vehicleId]);
    
    if (result.affectedRows === 0) {
      return res.status(404).json({ message: '车辆不存在' });
    }
    
    res.json({ message: '车辆删除成功' });
  } catch (error) {
    res.status(500).json({ message: '删除车辆失败', error: error.message });
  }
});

// 通过车牌号查找车辆
router.get('/plate/:plateNumber', async (req, res) => {
  try {
    const plateNumber = req.params.plateNumber;
    const vehicles = await query('SELECT * FROM vehicles WHERE plate_number = ?', [plateNumber]);
    
    if (vehicles.length === 0) {
      return res.status(404).json({ message: '车辆不存在' });
    }
    
    res.json(vehicles[0]);
  } catch (error) {
    res.status(500).json({ message: '查找车辆失败', error: error.message });
  }
});

module.exports = router; 