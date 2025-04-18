const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const dotenv = require('dotenv');
const path = require('path');
const fs = require('fs');

// 加载环境变量
dotenv.config();

// 确保config目录存在
const configDir = path.join(__dirname, 'config');
if (!fs.existsSync(configDir)) {
  fs.mkdirSync(configDir, { recursive: true });
  console.log('创建config目录:', configDir);
}

// 检查数据库配置文件
const dbConfigPath = path.join(configDir, 'db.js');
if (!fs.existsSync(dbConfigPath)) {
  console.log('db.js文件不存在，创建默认配置文件');
  
  const defaultDbConfig = `
const mysql = require('mysql2/promise');
const dotenv = require('dotenv');

// 加载环境变量
dotenv.config();

// 数据库配置
const dbConfig = {
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'HYTT',
  password: process.env.DB_PASSWORD || 'mysqlpasswd',
  database: process.env.DB_NAME || 'hytt',
  port: parseInt(process.env.DB_PORT || '3306'),
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
  dateStrings: true
};

// 创建连接池
const pool = mysql.createPool(dbConfig);

// 模拟数据
const mockData = {
  notices: [
    {
      id: 1,
      title: '系统公告',
      content: '欢迎使用慧眼通途预约系统',
      publish_time: new Date(),
      is_important: 1,
      status: 1
    }
  ],
  banners: []
};

// 测试数据库连接
async function testConnection() {
  try {
    const connection = await pool.getConnection();
    connection.release();
    return true;
  } catch (error) {
    console.error('数据库连接失败:', error.message);
    return false;
  }
}

// 执行查询
async function query(sql, params = []) {
  try {
    const [results] = await pool.execute(sql, params);
    return results;
  } catch (error) {
    console.error('查询失败:', error.message);
    return [];
  }
}

module.exports = {
  query,
  testConnection,
  pool,
  mockData
};`;

  fs.writeFileSync(dbConfigPath, defaultDbConfig);
  console.log('已创建默认数据库配置文件');
}

// 安全地加载数据库模块
let dbModule;
try {
  dbModule = require('./config/db');
  console.log('数据库模块加载成功');
} catch (error) {
  console.error('加载数据库模块失败:', error.message);
  console.log('使用模拟数据库模块');
  
  // 创建模拟数据库模块
  dbModule = {
    query: async (sql, params = []) => {
      console.log('执行模拟查询:', sql);
      return [];
    },
    testConnection: async () => false,
    mockData: {
      notices: [],
      banners: []
    }
  };
}

// 导出数据库模块供其他文件使用
const { testConnection } = dbModule;

// 创建Express应用
const app = express();

// CORS配置 - 修改为更详细的配置
const corsOptions = {
  origin: '*', // 允许所有来源访问
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With', 'Cache-Control'],
  credentials: true,
  maxAge: 86400 // 预检请求结果缓存1天
};
app.use(cors(corsOptions));

// 处理OPTIONS请求
app.options('*', cors(corsOptions));

// 请求体解析
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// 配置静态文件服务
// 设置多个静态文件目录
app.use('/static', express.static(path.join(__dirname, '../static'))); // 客户端目录下的static文件夹
app.use('/static', express.static(path.join(__dirname, 'static'))); // 服务器目录下的static文件夹
// 移除额外的静态文件路径映射，避免重复
// app.use('/static/images', express.static(path.join(__dirname, 'static/images'))); // 图片目录

// 确保静态文件目录存在
const staticDir = path.join(__dirname, 'static');
const staticImagesDir = path.join(__dirname, 'static/images');

// 创建静态文件目录（如果不存在）
if (!fs.existsSync(staticDir)) {
  fs.mkdirSync(staticDir, { recursive: true });
  console.log('创建static目录:', staticDir);
}

// 创建图片目录（如果不存在）
if (!fs.existsSync(staticImagesDir)) {
  fs.mkdirSync(staticImagesDir, { recursive: true });
  console.log('创建static/images目录:', staticImagesDir);
}

// 导入路由
const userRoutes = require('./routes/users');
const vehicleRoutes = require('./routes/vehicles');
const bookingRoutes = require('./routes/bookings');
const vehicleAppointmentRoutes = require('./routes/vehicleAppointments');
const dbTestRoutes = require('./routes/dbTest');
const bannerRoutes = require('./routes/banners');
const noticeRoutes = require('./routes/notices');

// 使用路由 - 确保所有路由都使用相对路径
app.use('/api/users', userRoutes);
app.use('/api/vehicles', vehicleRoutes);
app.use('/api/bookings', bookingRoutes);
app.use('/api/vehicle-appointments', vehicleAppointmentRoutes);
app.use('/api/db-test', dbTestRoutes);
app.use('/api/banners', bannerRoutes);
app.use('/api/notices', noticeRoutes);

// 根路由
app.get('/', (req, res) => {
  res.json({ message: '欢迎使用微信小程序后端API' });
});

// 添加API状态检查路由
app.get('/api/status', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    server: {
      nodeVersion: process.version,
      platform: process.platform,
      uptime: process.uptime(),
      memoryUsage: process.memoryUsage()
    },
    endpoints: [
      { path: '/api/users', methods: ['GET', 'POST'] },
      { path: '/api/vehicles', methods: ['GET', 'POST'] },
      { path: '/api/bookings', methods: ['GET', 'POST'] },
      { path: '/api/vehicle-appointments', methods: ['GET', 'POST'] },
      { path: '/api/banners', methods: ['GET'] },
      { path: '/api/notices', methods: ['GET'] }
    ]
  });
});

// 全局错误处理中间件
app.use((err, req, res, next) => {
  console.error('服务器错误:', err.stack);
  res.status(500).json({
    message: '服务器内部错误',
    error: process.env.NODE_ENV === 'development' ? err.message : '请联系管理员'
  });
});

// 404处理中间件
app.use((req, res) => {
  res.status(404).json({ message: '请求的资源不存在' });
});

// 启动服务器
const PORT = process.env.PORT || 3000;
app.listen(PORT, async () => {
  console.log(`服务器运行在端口 ${PORT}`);
  
  // 测试数据库连接
  try {
    const isConnected = await testConnection();
    if (isConnected) {
      console.log('数据库连接成功！');
      console.log(`数据库信息: ${process.env.DB_USER}@${process.env.DB_HOST}:${process.env.DB_PORT}/${process.env.DB_NAME}`);
    } else {
      console.error('数据库连接失败！请检查数据库配置。');
    }
  } catch (error) {
    console.error('数据库连接测试发生错误:', error.message);
  }
}); 