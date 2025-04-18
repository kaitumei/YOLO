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
  connectTimeout: 10000, // 增加连接超时时间
  charset: 'utf8mb4'
};

// 备用数据库配置（尝试直接连接服务器IP）
const backupDbConfig = {
  host: '117.72.120.52', // 直接使用服务器IP
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

// 打印数据库配置（排除敏感信息）
console.log(`主数据库配置: ${dbConfig.host}:${dbConfig.port}/${dbConfig.database}`);
console.log(`备用数据库配置: ${backupDbConfig.host}:${backupDbConfig.port}/${backupDbConfig.database}`);

// 创建主数据库连接池
const pool = mysql.createPool(dbConfig);
// 创建备用数据库连接池
const backupPool = mysql.createPool(backupDbConfig);

// 模拟数据 - 用于开发和测试
const mockData = {
  notices: [
    {
      id: 1,
      title: '系统公告 - 测试数据',
      content: '这是一条测试公告，当数据库连接失败时显示。',
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
  banners: [
    {
      id: 1,
      title: '慧眼通途欢迎您',
      image_url: '/static/images/banner1.jpg',
      link_url: '',
      sort_order: 1,
      status: 1
    },
    {
      id: 2,
      title: '智能预约系统',
      image_url: '/static/images/banner2.jpg',
      link_url: '',
      sort_order: 2,
      status: 1
    }
  ]
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
    console.error('主数据库连接失败:', mainError);
    
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
      console.error('备用数据库连接也失败:', backupError);
      isDbConnected = false;
      usingBackupConnection = false;
      return false;
    }
  }
}

// 定期测试数据库连接，每30秒尝试一次
setInterval(async () => {
  try {
    await testConnection();
    console.log(`[${new Date().toISOString()}] 数据库连接状态: ${isDbConnected ? '已连接' : '未连接'}, 使用备用连接: ${usingBackupConnection}`);
  } catch (err) {
    console.error(`[${new Date().toISOString()}] 测试数据库连接时出错:`, err);
  }
}, 30000);

// 执行SQL查询的辅助函数
async function query(sql, params = []) {
  try {
    // 记录查询语句
    const queryStart = Date.now();
    console.log(`[${new Date().toISOString()}] 执行SQL: ${sql}`);
    
    // 检查和清理参数
    const cleanParams = params.map(param => {
      if (typeof param === 'string' && /^\d+$/.test(param)) {
        // 如果参数是看起来像数字的字符串，转为数字
        return parseInt(param, 10);
      }
      return param;
    });
    
    // 每次查询前检查数据库连接状态
    if (!isDbConnected) {
      console.log('数据库未连接，尝试连接...');
      await testConnection();
    }
    
    // 尝试从真实数据库获取数据
    if (isDbConnected) {
      try {
        // 获取连接，根据连接状态选择主连接或备用连接
        const currentPool = usingBackupConnection ? backupPool : pool;
        const connection = await currentPool.getConnection();
        
        try {
          let results;
          
          // 检查是否有参数绑定
          if (sql.includes('?') && cleanParams.length > 0) {
            // 使用参数化查询
            [results] = await connection.execute(sql, cleanParams);
          } else {
            // 直接执行SQL，不使用参数绑定
            [results] = await connection.query(sql);
          }
          
          const queryTime = Date.now() - queryStart;
          console.log(`SQL查询成功: 耗时${queryTime}ms, 返回 ${results ? results.length : 0} 条记录`);
          
          // 释放连接
          connection.release();
          
          // 直接返回数据库查询结果，不使用模拟数据
          return results;
        } catch (dbError) {
          // 释放连接
          connection.release();
          console.error('数据库查询错误:', dbError);
          
          // 尝试不带参数的简单查询
          if (sql.includes('?') && params.length > 0) {
            console.log('尝试使用替换后的SQL语句重新查询');
            // 替换所有参数占位符为实际值
            let statementWithValues = sql;
            cleanParams.forEach(param => {
              statementWithValues = statementWithValues.replace('?', 
                typeof param === 'string' ? `'${param}'` : param);
            });
            
            console.log('替换后的SQL:', statementWithValues);
            
            // 重新获取连接
            const retryConnection = await currentPool.getConnection();
            try {
              // 直接执行替换后的SQL
              const [retryResults] = await retryConnection.query(statementWithValues);
              retryConnection.release();
              return retryResults;
            } catch (retryError) {
              retryConnection.release();
              console.error('重试查询也失败:', retryError);
              // 继续返回空结果
            }
          }
          
          // 对于查询操作，返回空数组
          if (sql.trim().toLowerCase().startsWith('select')) {
            return [];
          }
          
          // 对于非查询操作，构造一个模拟的结果
          return { affectedRows: 0, insertId: 0 };
        }
      } catch (connectionError) {
        console.error('获取数据库连接失败:', connectionError);
        
        // 对于查询操作，返回空数组
        if (sql.trim().toLowerCase().startsWith('select')) {
          return [];
        }
        
        // 对于非查询操作，构造一个模拟的结果
        return { affectedRows: 0, insertId: 0 };
      }
    }
    
    // 数据库未连接，返回空结果
    console.log('数据库未连接，返回空结果');
    
    // 对于查询操作，返回空数组
    if (sql.trim().toLowerCase().startsWith('select')) {
      return [];
    }
    
    // 对于非查询操作，构造一个模拟的结果
    return { affectedRows: 0, insertId: 0 };
  } catch (error) {
    console.error('SQL查询错误:', error);
    
    // 默认返回空数组
    if (sql.trim().toLowerCase().startsWith('select')) {
      return [];
    }
    
    // 对于非查询操作，构造一个模拟的结果
    return { affectedRows: 0, insertId: 0 };
  }
}

// 立即测试连接
testConnection();

module.exports = {
  query,
  testConnection,
  pool,
  backupPool,
  mockData // 导出模拟数据以便其他模块使用
}; 