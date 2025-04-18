// 插入公告数据的脚本
const mysql = require('mysql2/promise');
require('dotenv').config();

// 数据库配置
const dbConfig = {
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'HYTT',
  password: process.env.DB_PASSWORD || 'mysqlpasswd',
  database: process.env.DB_NAME || 'hytt',
  port: parseInt(process.env.DB_PORT || '3306'),
  waitForConnections: true,
  connectionLimit: 1,
  queueLimit: 0
};

// 备用数据库配置
const backupDbConfig = {
  host: '117.72.120.52',
  user: process.env.DB_USER || 'HYTT',
  password: process.env.DB_PASSWORD || 'mysqlpasswd',
  database: process.env.DB_NAME || 'hytt',
  port: parseInt(process.env.DB_PORT || '3306'),
  waitForConnections: true,
  connectionLimit: 1,
  queueLimit: 0
};

// 要插入的公告数据
const noticesData = [
  {
    title: '系统维护通知',
    content: '尊敬的用户，我们的系统将于2023年5月15日凌晨2:00-4:00进行例行维护，期间部分功能可能无法正常使用。给您带来的不便，敬请谅解。',
    publish_time: new Date(),
    is_important: 1,
    status: 1
  },
  {
    title: '五一假期预约变更通知',
    content: '尊敬的用户，五一假期(5月1日-5月5日)期间，园区预约规则调整为每日限量100个预约名额。同时，园区开放时间延长至晚上8:00。欢迎您的到来。',
    publish_time: new Date(),
    is_important: 1,
    status: 1
  },
  {
    title: '园区设施更新完成',
    content: '通知：园区主楼设施已完成更新，现已增设自助服务终端3台，休息区2处，饮水点4处，可更好地为您提供便捷服务。',
    publish_time: new Date(),
    is_important: 0,
    status: 1
  },
  {
    title: '新版系统上线公告',
    content: '欢迎使用慧眼通途预约系统V2.0版本。本次更新优化了预约流程，新增了车辆管理功能，修复了已知问题。如有使用问题，请联系客服。',
    publish_time: new Date(),
    is_important: 0,
    status: 1
  },
  {
    title: '用户须知更新',
    content: '重要提示：为保障园区安全和服务质量，自2023年6月1日起，所有访客需要提前24小时完成线上预约，临时访问需到前台登记并验证身份信息。感谢您的理解与配合。',
    publish_time: new Date(),
    is_important: 1,
    status: 1
  }
];

// 插入公告数据的函数
async function insertNotices() {
  let connection;
  let pool;
  let isBackup = false;
  
  try {
    console.log('尝试连接主数据库...');
    pool = mysql.createPool(dbConfig);
    connection = await pool.getConnection();
    console.log('主数据库连接成功');
  } catch (mainError) {
    console.error('主数据库连接失败:', mainError);
    
    try {
      console.log('尝试连接备用数据库...');
      pool = mysql.createPool(backupDbConfig);
      connection = await pool.getConnection();
      console.log('备用数据库连接成功');
      isBackup = true;
    } catch (backupError) {
      console.error('备用数据库连接也失败:', backupError);
      console.error('无法连接数据库，程序终止');
      process.exit(1);
    }
  }
  
  try {
    console.log(`开始向${isBackup ? '备用' : '主'}数据库插入公告数据...`);
    
    // 检查notices表是否存在
    const [tables] = await connection.query(`
      SHOW TABLES LIKE 'notices'
    `);
    
    if (tables.length === 0) {
      console.log('notices表不存在，创建表');
      await connection.query(`
        CREATE TABLE notices (
          id INT AUTO_INCREMENT PRIMARY KEY,
          title VARCHAR(255) NOT NULL,
          content TEXT,
          publish_time DATETIME,
          end_time DATETIME,
          is_important TINYINT(1) DEFAULT 0,
          status TINYINT(1) DEFAULT 1,
          create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
          update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
      `);
      console.log('notices表创建成功');
    }
    
    // 清空现有数据（可选，根据需要取消注释）
    // await connection.query('TRUNCATE TABLE notices');
    // console.log('已清空现有公告数据');
    
    // 插入公告数据
    for (const notice of noticesData) {
      try {
        // 使用直接值替换而不是参数绑定，避免参数类型问题
        const insertSql = `
          INSERT INTO notices (title, content, publish_time, is_important, status)
          VALUES ('${notice.title.replace(/'/g, "''")}', 
                  '${notice.content.replace(/'/g, "''")}', 
                  '${notice.publish_time.toISOString().slice(0, 19).replace('T', ' ')}', 
                  ${notice.is_important}, 
                  ${notice.status})
        `;
        
        await connection.query(insertSql);
        console.log(`成功插入公告: ${notice.title}`);
      } catch (insertError) {
        console.error(`插入公告"${notice.title}"失败:`, insertError.message);
        
        // 尝试使用参数绑定方式
        try {
          console.log('尝试使用参数绑定方式插入...');
          await connection.execute(`
            INSERT INTO notices (title, content, publish_time, is_important, status)
            VALUES (?, ?, ?, ?, ?)
          `, [
            notice.title,
            notice.content,
            notice.publish_time,
            parseInt(notice.is_important, 10),
            parseInt(notice.status, 10)
          ]);
          console.log(`使用参数绑定方式成功插入公告: ${notice.title}`);
        } catch (retryError) {
          console.error(`使用参数绑定方式插入"${notice.title}"也失败:`, retryError.message);
        }
      }
    }
    
    console.log('所有公告数据插入成功');
  } catch (error) {
    console.error('插入公告数据时出错:', error);
  } finally {
    if (connection) {
      connection.release();
      console.log('数据库连接已释放');
    }
    if (pool) {
      pool.end();
      console.log('连接池已关闭');
    }
  }
}

// 执行插入操作
insertNotices()
  .then(() => {
    console.log('脚本执行完成');
    process.exit(0);
  })
  .catch(err => {
    console.error('脚本执行失败:', err);
    process.exit(1);
  }); 