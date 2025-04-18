// 检查并修复config目录和数据库配置
const fs = require('fs');
const path = require('path');

console.log('开始修复配置目录和数据库配置文件...');

// 检查app目录结构
console.log('当前目录:', process.cwd());
console.log('目录内容:', fs.readdirSync('.').join(', '));

// 确保config目录存在
if (!fs.existsSync('./config')) {
  console.log('config目录不存在，创建目录');
  fs.mkdirSync('./config', { recursive: true });
} else {
  console.log('config目录已存在');
  console.log('config目录内容:', fs.readdirSync('./config').join(', '));
}

// 检查数据库配置文件
const dbConfigPath = './config/db.js';
if (!fs.existsSync(dbConfigPath)) {
  console.log('数据库配置文件不存在，创建文件');
  
  // 创建默认数据库配置文件
  const dbConfigContent = `
const mysql = require('mysql2/promise');
const dotenv = require('dotenv');

// 加载环境变量
dotenv.config();

// 主数据库配置
const dbConfig = {
  host: process.env.DB_HOST || 'localhost', 
  user: process.env.DB_USER || 'HYTT',
  password: process.env.DB_PASSWORD || 'mysqlpasswd',
  database: process.env.DB_NAME || 'hytt',
  port: parseInt(process.env.DB_PORT || '3306'),
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
  dateStrings: true,
  connectTimeout: 10000,
  charset: 'utf8mb4'
};

// 备用数据库配置
const backupDbConfig = {
  host: '117.72.120.52',
  user: process.env.DB_USER || 'HYTT',
  password: process.env.DB_PASSWORD || 'mysqlpasswd',
  database: process.env.DB_NAME || 'hytt',
  port: parseInt(process.env.DB_PORT || '3306'),
  waitForConnections: true,
  connectionLimit: 5,
  queueLimit: 0,
  dateStrings: true,
  connectTimeout: 10000,
  charset: 'utf8mb4'
};

console.log(\`主数据库配置: \${dbConfig.host}:\${dbConfig.port}/\${dbConfig.database}\`);
console.log(\`备用数据库配置: \${backupDbConfig.host}:\${backupDbConfig.port}/\${backupDbConfig.database}\`);

// 创建连接池
const pool = mysql.createPool(dbConfig);
const backupPool = mysql.createPool(backupDbConfig);

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
    },
    {
      id: 2,
      title: '使用指南',
      content: '请按照预约流程完成操作，如有问题请联系管理员。',
      publish_time: new Date(),
      is_important: 0,
      status: 1
    }
  ],
  banners: []
};

// 测试数据库连接
let isDbConnected = false;
let usingBackupConnection = false;

async function testConnection() {
  try {
    // 先尝试主连接
    console.log('尝试连接主数据库...');
    const connection = await pool.getConnection();
    console.log('主数据库连接成功');
    connection.release();
    isDbConnected = true;
    usingBackupConnection = false;
    return true;
  } catch (mainError) {
    console.error('主数据库连接失败:', mainError.message);
    
    try {
      // 尝试备用连接
      console.log('尝试连接备用数据库...');
      const backupConnection = await backupPool.getConnection();
      console.log('备用数据库连接成功');
      backupConnection.release();
      isDbConnected = true;
      usingBackupConnection = true;
      return true;
    } catch (backupError) {
      console.error('备用数据库连接也失败:', backupError.message);
      isDbConnected = false;
      usingBackupConnection = false;
      return false;
    }
  }
}

// 执行SQL查询的辅助函数
async function query(sql, params = []) {
  try {
    // 记录查询语句
    console.log(\`执行SQL: \${sql}\`);
    
    // 每次查询前检查数据库连接状态
    if (!isDbConnected) {
      console.log('数据库未连接，尝试连接...');
      await testConnection();
    }
    
    // 尝试从真实数据库获取数据
    if (isDbConnected) {
      try {
        // 获取连接
        const currentPool = usingBackupConnection ? backupPool : pool;
        const connection = await currentPool.getConnection();
        
        try {
          // 执行查询
          const [results] = await connection.execute(sql, params);
          console.log(\`SQL查询成功: 返回 \${results ? results.length : 0} 条记录\`);
          
          // 释放连接
          connection.release();
          
          return results;
        } catch (dbError) {
          // 释放连接
          connection.release();
          console.error('数据库查询错误:', dbError.message);
          
          // 返回空数组
          return [];
        }
      } catch (connectionError) {
        console.error('获取数据库连接失败:', connectionError.message);
        return [];
      }
    }
    
    // 数据库未连接，返回空结果
    console.log('数据库未连接，返回空结果');
    return [];
  } catch (error) {
    console.error('SQL查询错误:', error.message);
    return [];
  }
}

// 立即测试连接
testConnection().catch(err => console.error('连接测试失败:', err.message));

module.exports = {
  query,
  testConnection,
  pool,
  backupPool,
  mockData // 导出模拟数据以便其他模块使用
};`;

  fs.writeFileSync(dbConfigPath, dbConfigContent);
  console.log('已创建默认数据库配置文件');
} else {
  console.log('数据库配置文件已存在');
}

// 修改start.js文件使其在启动前运行修复脚本
const startJsPath = './start.js';
if (fs.existsSync(startJsPath)) {
  console.log('修改start.js文件，添加配置检查');
  
  let startJsContent = fs.readFileSync(startJsPath, 'utf8');
  
  // 检查是否已经添加了修复逻辑
  if (!startJsContent.includes('// 配置检查已添加')) {
    // 在文件开头添加配置检查
    startJsContent = `// 配置检查已添加
try {
  // 确保配置目录和文件存在
  require('./fix-config');
  console.log('配置检查完成');
} catch (error) {
  console.error('配置检查失败:', error);
}

${startJsContent}`;
    
    fs.writeFileSync(startJsPath, startJsContent);
    console.log('已更新start.js文件');
  } else {
    console.log('start.js文件已包含配置检查');
  }
} else {
  console.log('start.js文件不存在');
}

console.log('配置修复完成'); 